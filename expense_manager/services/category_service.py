from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from expense_manager.constants.default_categories import DEFAULT_CATEGORIES

from expense_manager.services.exceptions import (
    CategoryAlreadyExistsError,
    CategoryNotFoundError,
    CategoryInUseError,
)
from expense_manager.utils.logger import logger
from expense_manager.utils.helpers import escape_like


class CategoryService:
    """Business service for Category operations.

    Categories live in a shared, guardian-owned pool (the ``dependent``
    field on the Category DocType is legacy and unused). Which categories a
    dependent may use is governed by the dependent's ``allowed_categories``
    child table — see ``DependentService``. Category ownership here is
    purely ``doc.owner_user == guardian``.
    """

    @staticmethod
    def create_category(
        owner_user: str,
        category_name: str,
        icon: Optional[str] = None,
    ) -> Document:
        """
        Create a new category for a user.

        Raises:
            CategoryAlreadyExistsError
        """

        category_name = CategoryService._normalize_name(category_name)

        if CategoryService.category_exists(
            owner_user,
            category_name,
        ):
            raise CategoryAlreadyExistsError(
                _("Category '{0}' already exists.").format(category_name)
            )

        category = frappe.get_doc(
            {
                "doctype": "Category",
                "owner_user": owner_user,
                "category_name": category_name,
                "icon": icon,
                "is_active": 1,
            },
            ignore_permissions=True,
        )

        category.insert(ignore_permissions=True)

        logger.info(
            "Category created | owner=%s | category=%s | id=%s",
            owner_user,
            category.category_name,
            category.name,
        )

        return category

    @staticmethod
    def get_category(
        owner_user: str,
        category: str,
    ) -> Document:
        """
        Return a category owned by the given user.
        """
        return CategoryService._get_category(
            owner_user,
            category,
        )

    @staticmethod
    def category_exists(
        owner_user: str,
        category_name: str,
    ) -> bool:
        """
        Check whether a category already exists for a user.
        """

        category_name = CategoryService._normalize_name(category_name)

        filters = {
            "owner_user": owner_user,
            "category_name": category_name,
        }

        return bool(
            frappe.db.exists(
                "Category",
                filters,
            )
        )

    @staticmethod
    def _get_category(
        owner_user: str,
        category: str,
    ) -> Document:
        """
        Fetch a category and verify ownership.
        """

        try:
            doc = frappe.get_doc("Category", category, ignore_permissions=True)

        except frappe.DoesNotExistError:
            raise CategoryNotFoundError(
                _("Category not found.")
            )

        if doc.owner_user != owner_user:
            raise CategoryNotFoundError(
                _("Category not found.")
            )

        return doc

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Remove extra whitespace and convert to title case.
        """

        return " ".join(name.strip().split()).title()

    @staticmethod
    def update_category(
        owner_user: str,
        category: str,
        category_name: str | None = None,
        icon: str | None = None,
        is_active: bool | None = None,
    ) -> Document:
        """
        Update an existing category.
        """

        doc = CategoryService._get_category(
            owner_user,
            category,
        )

        if category_name is not None:
            category_name = CategoryService._normalize_name(category_name)

            if (
                category_name != doc.category_name
                and CategoryService.category_exists(
                    owner_user,
                    category_name,
                )
            ):
                raise CategoryAlreadyExistsError(
                    _("Category '{0}' already exists.").format(
                        category_name
                    )
                )

            doc.category_name = category_name

        if icon is not None:
            doc.icon = icon

        if is_active is not None:
            doc.is_active = is_active

        doc.save(ignore_permissions=True)

        logger.info(
            "Category updated | owner=%s | id=%s",
            owner_user,
            doc.name,
        )

        return doc

    @staticmethod
    def archive_category(
        owner_user: str,
        category: str,
    ) -> Document:
        """
        Archive a category.
        """
        return CategoryService._set_active_status(
            owner_user,
            category,
            False,
        )

    @staticmethod
    def restore_category(
        owner_user: str,
        category: str,
    ) -> Document:
        """
        Restore an archived category.
        """
        return CategoryService._set_active_status(
            owner_user,
            category,
            True,
        )

    @staticmethod
    def list_categories(
        owner_user: str,
        active_only: bool = False,
    ) -> list[dict]:
        """
        List all categories belonging to a user.
        """

        filters = {
            "owner_user": owner_user,
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Category",
            filters=filters,
            fields=[
                "name",
                "category_name",
                "icon",
                "is_active",
                "creation",
                "modified",
            ],
            order_by="category_name asc",
        )

    @staticmethod
    def search_categories(
        owner_user: str,
        search_text: str,
        active_only: bool = True,
    ) -> list[dict]:
        """
        Search categories by name.
        """

        filters = {
            "owner_user": owner_user,
            "category_name": [
                "like",
                f"%{escape_like(search_text.strip())}%",
            ],
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Category",
            filters=filters,
            fields=[
                "name",
                "category_name",
                "icon",
                "is_active",
            ],
            order_by="category_name asc",
        )

    @staticmethod
    def delete_category(
        owner_user: str,
        category: str,
    ) -> None:
        """
        Delete a category after ensuring it is not in use.
        """

        doc = CategoryService._get_category(
            owner_user,
            category,
        )

        CategoryService._validate_delete(doc)

        doc.delete(ignore_permissions=True)

        logger.info(
            "Category deleted | owner=%s | id=%s",
            owner_user,
            doc.name,
        )

    @staticmethod
    def create_default_categories(
        owner_user: str,
    ) -> list[Document]:
        """
        Create the default categories for a user.
        Existing categories are skipped.
        """

        created = []

        for category_name, icon in DEFAULT_CATEGORIES:
            if CategoryService.category_exists(
                owner_user,
                category_name,
            ):
                continue

            created.append(
                CategoryService.create_category(
                    owner_user=owner_user,
                    category_name=category_name,
                    icon=icon,
                )
            )

        return created

    @staticmethod
    def _set_active_status(
        owner_user: str,
        category: str,
        is_active: bool,
    ) -> Document:
        """
        Update a category's active status.
        """

        doc = CategoryService._get_category(
            owner_user,
            category,
        )

        if doc.is_active == is_active:
            return doc

        doc.is_active = is_active
        doc.save(ignore_permissions=True)

        logger.info(
            "Category %s | owner=%s | id=%s",
            "restored" if is_active else "archived",
            owner_user,
            doc.name,
        )

        return doc

    @staticmethod
    def _validate_delete(
        category: Document,
    ) -> None:
        """
        Ensure the category is safe to delete.
        """

        if frappe.db.exists(
            "Expense",
            {
                "category": category.name,
            },
        ):
            raise CategoryInUseError(
                _("Cannot delete category because it is used by one or more expenses.")
            )

        if frappe.db.exists(
            "Budget",
            {
                "category": category.name,
            },
        ):
            raise CategoryInUseError(
                _("Cannot delete category because it is used by one or more budgets.")
            )
