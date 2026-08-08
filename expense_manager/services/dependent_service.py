from __future__ import annotations

from typing import Optional, Any

import frappe
from frappe import _
from frappe.model.document import Document

from expense_manager.services.exceptions import (
    CategoryNotFoundError,
    DependentAlreadyExistsError,
    DependentNotFoundError,
    DependentInUseError,
    InvalidRelationshipError,
    InvalidAllowanceError,
)
from expense_manager.services.category_service import CategoryService
from expense_manager.constants.dependent import Relationship
from expense_manager.utils.logger import logger
from expense_manager.utils.helpers import escape_like


_UNSET = object()


class DependentService:

    @staticmethod
    def list_allowed_categories(
        guardian: str,
        dependent: str,
        active_only: bool = True,
    ) -> list[dict]:
        """List the categories a dependent is allowed to use.

        Categories are a shared, guardian-owned pool. An empty
        ``allowed_categories`` child table means the dependent may use ALL of
        the guardian's active categories (the default until the guardian
        explicitly customizes the list). This method is the single source of
        truth for the "empty table = all allowed" fallback; other callers
        (AI vocabulary loading, Telegram category listing) delegate here.
        """
        doc = DependentService._get_dependent(guardian, dependent)

        all_cats = CategoryService.list_categories(guardian, active_only=active_only)
        by_id = {row["name"]: row for row in all_cats}

        allowed_rows = [
            row
            for row in (doc.get("allowed_categories") or [])
            if (not active_only or row.get("is_active"))
        ]

        if not allowed_rows:
            return all_cats

        return [by_id[row.get("category")] for row in allowed_rows if row.get("category") in by_id]

    @staticmethod
    def add_allowed_category(
        guardian: str,
        dependent: str,
        category: str,
    ) -> Document:
        """Explicitly allow a guardian-owned category for a dependent.

        ``category`` may be a Category doc name or a category name. Idempotent:
        adding a category that is already in the allowed list is a no-op.
        """
        doc = DependentService._get_dependent(guardian, dependent)
        category_id = DependentService._resolve_category_id(guardian, category)

        existing = [row for row in (doc.get("allowed_categories") or []) if row.get("category") == category_id]
        if existing:
            return doc

        doc.append("allowed_categories", {"category": category_id, "is_active": 1})
        doc.save(ignore_permissions=True)

        logger.info(
            "Dependent allowed category added | guardian=%s | dependent=%s | category=%s",
            guardian,
            dependent,
            category_id,
        )

        return doc

    @staticmethod
    def remove_allowed_category(
        guardian: str,
        dependent: str,
        category: str,
    ) -> Document:
        """Revoke an allowed category from a dependent's list."""
        doc = DependentService._get_dependent(guardian, dependent)
        category_id = DependentService._resolve_category_id(guardian, category)

        for row in list(doc.get("allowed_categories") or []):
            if row.get("category") == category_id:
                doc.remove(row)

        doc.save(ignore_permissions=True)

        logger.info(
            "Dependent allowed category removed | guardian=%s | dependent=%s | category=%s",
            guardian,
            dependent,
            category_id,
        )

        return doc

    @staticmethod
    def _resolve_category_id(guardian: str, category: Any) -> str:
        """Resolve a category supplied by a client to its doc name.

        Accepts either an existing Category doc name (ownership still
        validated) or a case-insensitive match against the guardian's
        category names. Handles string, dict, or object inputs safely.
        """
        if isinstance(category, dict):
            category = category.get("name") or category.get("category") or category.get("category_name") or ""
        if not isinstance(category, str):
            category = str(category) if category is not None else ""
        category_str = category.strip()
        if not category_str:
            raise CategoryNotFoundError(_("Category is required."))

        if frappe.db.exists("Category", category_str):
            return CategoryService.get_category(guardian, category_str).name

        for cat in CategoryService.list_categories(guardian):
            if cat["category_name"].lower() == category_str.lower():
                return cat["name"]

        raise CategoryNotFoundError(
            _("Category '{0}' not found. Please use an existing category name.").format(category_str)
        )

    @staticmethod
    def create_dependent(
        guardian: str,
        dependent_name: str,
        relationship: str,
        default_monthly_allowance: float,
        telegram_username: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        allow_carry_forward: bool = True,
    ) -> Document:
        dependent_name = DependentService._normalize_name(dependent_name)

        DependentService._validate_relationship(relationship)
        default_monthly_allowance = DependentService._validate_allowance(
            default_monthly_allowance
        )

        if DependentService.dependent_exists(guardian, dependent_name):
            raise DependentAlreadyExistsError(
                _("Dependent '{0}' already exists.").format(dependent_name)
            )

        dependent = frappe.get_doc(
            {
                "doctype": "Dependent",
                "guardian": guardian,
                "dependent_name": dependent_name,
                "relationship": relationship,
                "default_monthly_allowance": default_monthly_allowance,
                "telegram_username": telegram_username,
                "telegram_user_id": telegram_user_id,
                "allow_carry_forward": allow_carry_forward,
                "is_active": 1,
            },
            ignore_permissions=True,
        )

        dependent.insert(ignore_permissions=True)

        logger.info(
            "Dependent created | guardian=%s | name=%s | id=%s",
            guardian,
            dependent.dependent_name,
            dependent.name,
        )

        return dependent

    @staticmethod
    def get_dependent(
        guardian: str,
        dependent: str,
    ) -> Document:
        return DependentService._get_dependent(guardian, dependent)

    @staticmethod
    def dependent_exists(
        guardian: str,
        dependent_name: str,
    ) -> bool:
        dependent_name = DependentService._normalize_name(dependent_name)

        return bool(
            frappe.db.exists(
                "Dependent",
                {
                    "guardian": guardian,
                    "dependent_name": dependent_name,
                },
            )
        )

    @staticmethod
    def update_dependent(
        guardian: str,
        dependent: str,
        dependent_name: Optional[str] = None,
        relationship: Optional[str] = None,
        default_monthly_allowance: Optional[float] = None,
        telegram_username: str | None | object = _UNSET,
        telegram_user_id: str | None | object = _UNSET,
        allow_carry_forward: Optional[bool] = None,
    ) -> Document:
        doc = DependentService._get_dependent(guardian, dependent)

        if dependent_name is not None:
            dependent_name = DependentService._normalize_name(dependent_name)

            if (
                dependent_name != doc.dependent_name
                and DependentService.dependent_exists(guardian, dependent_name)
            ):
                raise DependentAlreadyExistsError(
                    _("Dependent '{0}' already exists.").format(dependent_name)
                )

            doc.dependent_name = dependent_name

        if relationship is not None:
            DependentService._validate_relationship(relationship)
            doc.relationship = relationship

        if default_monthly_allowance is not None:
            doc.default_monthly_allowance = DependentService._validate_allowance(
                default_monthly_allowance
            )

        if telegram_username is not _UNSET:
            doc.telegram_username = telegram_username

        if telegram_user_id is not _UNSET:
            doc.telegram_user_id = telegram_user_id

        if allow_carry_forward is not None:
            doc.allow_carry_forward = allow_carry_forward

        doc.save(ignore_permissions=True)

        logger.info(
            "Dependent updated | guardian=%s | id=%s",
            guardian,
            doc.name,
        )

        return doc

    @staticmethod
    def archive_dependent(
        guardian: str,
        dependent: str,
    ) -> Document:
        return DependentService._set_active_status(guardian, dependent, False)

    @staticmethod
    def restore_dependent(
        guardian: str,
        dependent: str,
    ) -> Document:
        return DependentService._set_active_status(guardian, dependent, True)

    @staticmethod
    def list_dependents(
        guardian: str,
        active_only: bool = False,
    ) -> list[dict]:
        filters = {
            "guardian": guardian,
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Dependent",
            filters=filters,
            fields=[
                "name",
                "dependent_name",
                "relationship",
                "default_monthly_allowance",
                "allow_carry_forward",
                "is_active",
                "total_savings",
                "creation",
                "modified",
            ],
            order_by="dependent_name asc",
        )

    @staticmethod
    def search_dependents(
        guardian: str,
        search_text: Optional[str],
        active_only: bool = True,
    ) -> list[dict]:
        if not search_text:
            return []

        filters = {
            "guardian": guardian,
            "dependent_name": ["like", f"%{escape_like(search_text.strip())}%"],
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Dependent",
            filters=filters,
            fields=[
                "name",
                "dependent_name",
                "relationship",
                "is_active",
            ],
            order_by="dependent_name asc",
        )

    @staticmethod
    def get_active_dependent_by_telegram_id(
        telegram_user_id: str,
    ) -> Optional[dict]:
        """Resolve a Telegram user ID to an active dependent's name and guardian."""
        dependent_name = frappe.db.get_value(
            "Dependent",
            {
                "telegram_user_id": telegram_user_id,
                "is_active": 1,
            },
            "name",
        )

        if not dependent_name:
            return None

        guardian = frappe.db.get_value("Dependent", dependent_name, "guardian")
        return {"name": dependent_name, "guardian": guardian}

    @staticmethod
    def delete_dependent(
        guardian: str,
        dependent: str,
    ) -> None:
        doc = DependentService._get_dependent(guardian, dependent)

        DependentService._validate_delete(doc)

        doc.delete(ignore_permissions=True)

        logger.info(
            "Dependent deleted | guardian=%s | id=%s",
            guardian,
            doc.name,
        )

    @staticmethod
    def _get_dependent(
        guardian: str,
        dependent: str,
    ) -> Document:
        try:
            doc = frappe.get_doc("Dependent", dependent, ignore_permissions=True)

        except frappe.DoesNotExistError as exc:
            raise DependentNotFoundError(
                _("Dependent not found.")
            ) from exc

        if doc.guardian != guardian:
            raise DependentNotFoundError(
                _("Dependent not found.")
            )

        return doc

    @staticmethod
    def _set_active_status(
        guardian: str,
        dependent: str,
        is_active: bool,
    ) -> Document:
        doc = DependentService._get_dependent(guardian, dependent)

        if doc.is_active == is_active:
            return doc

        doc.is_active = is_active
        doc.save(ignore_permissions=True)

        logger.info(
            "Dependent %s | guardian=%s | id=%s",
            "restored" if is_active else "archived",
            guardian,
            doc.name,
        )

        return doc

    @staticmethod
    def _validate_delete(dependent: Document) -> None:
        if frappe.db.exists("Expense", {"dependent": dependent.name}):
            raise DependentInUseError(
                _("Cannot delete dependent because it is referenced by one or more expenses.")
            )

        if frappe.db.exists("Pocket Money Allocation", {"dependent": dependent.name}):
            raise DependentInUseError(
                _("Cannot delete dependent because it is referenced by one or more pocket money allocations.")
            )

    @staticmethod
    def _validate_relationship(relationship: str) -> None:
        valid_relationships = {item.value for item in Relationship}

        if relationship not in valid_relationships:
            raise InvalidRelationshipError(
                _("Invalid relationship '{0}'.").format(relationship)
            )

    @staticmethod
    def _validate_allowance(amount: float) -> float:
        if amount is None:
            raise InvalidAllowanceError(
                _("Default monthly allowance is required.")
            )

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidAllowanceError(
                _("Default monthly allowance must be numeric.")
            )

        if amount < 0:
            raise InvalidAllowanceError(
                _("Default monthly allowance must be zero or greater.")
            )

        return amount

    @staticmethod
    def _normalize_name(name: str) -> str:
        return " ".join(name.strip().split()).title()