from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document

from expense_manager.services.exceptions import (
    DependentAlreadyExistsError,
    DependentNotFoundError,
    DependentInUseError,
    InvalidRelationshipError,
    InvalidAllowanceError,
)
from expense_manager.constants.dependent import Relationship
from expense_manager.utils.logger import logger


_UNSET = object()


class DependentService:

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
            }
        )

        dependent.insert()

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

        doc.save()

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
            "dependent_name": ["like", f"%{search_text.strip()}%"],
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
    def delete_dependent(
        guardian: str,
        dependent: str,
    ) -> None:
        doc = DependentService._get_dependent(guardian, dependent)

        DependentService._validate_delete(doc)

        doc.delete()

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
            doc = frappe.get_doc("Dependent", dependent)

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
        doc.save()

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