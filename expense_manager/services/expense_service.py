from __future__ import annotations

from datetime import date
from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document

from expense_manager.services.exceptions import (
    CategoryNotAllowedError,
    ExpenseNotFoundError,
    InvalidExpenseAmountError,
    InvalidExpenseDateError,
    InvalidExpenseSourceError
)
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.constants.expense import ExpenseSource
from expense_manager.utils.logger import logger


_UNSET = object()


from frappe.utils import flt


class ExpenseService:

    @staticmethod
    def create_expense(
        owner_user: str,
        category: str,
        amount: float,
        expense_date: str | date,
        dependent: Optional[str] = None,
        description: Optional[str] = None,
        source: str = ExpenseSource.MANUAL,
        payment_method: Optional[str] = None,
        voice_transcript: Optional[str] = None,
    ) -> Document:
        ExpenseService._validate_category(owner_user, category, dependent=dependent)
        ExpenseService._validate_dependent(owner_user, dependent)
        ExpenseService._validate_dependent_category(owner_user, category, dependent)
        amount = ExpenseService._validate_amount(amount)
        ExpenseService._validate_expense_date(expense_date)
        ExpenseService._validate_source(source)

        expense = ExpenseService._create_doc(
            {
                "owner_user": owner_user,
                "category": category,
                "amount": amount,
                "expense_date": expense_date,
                "dependent": dependent,
                "description": description,
                "source": source,
                "payment_method": payment_method,
                "voice_transcript": voice_transcript,
            }
        )

        BudgetService.refresh_budget(owner_user, category, dependent=dependent)
        PocketMoneyService.refresh_balance(owner_user, dependent)

        logger.info(
            "Expense created | owner=%s | category=%s | dependent=%s | amount=%s | id=%s",
            owner_user,
            category,
            dependent,
            amount,
            expense.name,
        )

        return expense

    @staticmethod
    def get_expense(
        owner_user: str,
        expense: str,
    ) -> Document:
        return ExpenseService._get_expense(owner_user, expense)

    @staticmethod
    def update_expense(
        owner_user: str,
        expense: str,
        category: Optional[str] = None,
        amount: Optional[float] = None,
        expense_date: Optional[str | date] = None,
        dependent: str | None | object = _UNSET,
        description: str | None | object = _UNSET,
        payment_method: str | None | object = _UNSET,
    ) -> Document:
        doc = ExpenseService._get_expense(owner_user, expense)

        old_category = doc.category
        old_dependent = doc.dependent

        if category is not None:
            ExpenseService._validate_category(owner_user, category, dependent=doc.dependent)
            doc.category = category

        if dependent is not _UNSET:
            if dependent is not None:
                ExpenseService._validate_dependent(owner_user, dependent)
            doc.dependent = dependent

        if (category is not None or dependent is not _UNSET) and doc.dependent is not None:
            ExpenseService._validate_dependent_category(
                owner_user, doc.category, doc.dependent
            )

        if amount is not None:
            doc.amount = ExpenseService._validate_amount(amount)

        if expense_date is not None:
            ExpenseService._validate_expense_date(expense_date)
            doc.expense_date = expense_date

        if description is not _UNSET:
            doc.description = description

        if payment_method is not _UNSET:
            doc.payment_method = payment_method

        doc.save(ignore_permissions=True)

        BudgetService.refresh_budget(owner_user, old_category, dependent=old_dependent)
        if old_category != doc.category:
            BudgetService.refresh_budget(owner_user, doc.category, dependent=doc.dependent)

        PocketMoneyService.refresh_balance(owner_user, old_dependent)
        if old_dependent != doc.dependent:
            PocketMoneyService.refresh_balance(owner_user, doc.dependent)

        logger.info(
            "Expense updated | owner=%s | id=%s",
            owner_user,
            doc.name,
        )

        return doc

    @staticmethod
    def delete_expense(
        owner_user: str,
        expense: str,
    ) -> None:
        doc = ExpenseService._get_expense(owner_user, expense)

        owner = doc.owner_user
        category = doc.category
        dependent = doc.dependent
        expense_id = doc.name

        doc.delete(ignore_permissions=True)

        BudgetService.refresh_budget(owner, category, dependent=dependent)
        PocketMoneyService.refresh_balance(owner, dependent)

        logger.info(
            "Expense deleted | owner=%s | id=%s",
            owner,
            expense_id,
        )

    @staticmethod
    def list_expenses(
        owner_user: str,
        dependent: Optional[str | list] = None,
        category: Optional[str] = None,
        date_from: Optional[str | date] = None,
        date_to: Optional[str | date] = None,
        limit: Optional[int] = None,
    ) -> list[dict]:
        filters = {
            "owner_user": owner_user,
        }

        if dependent is not None:
            filters["dependent"] = dependent

        if category is not None:
            filters["category"] = category

        if date_from is not None and date_to is not None:
            filters["expense_date"] = ["between", [date_from, date_to]]
        elif date_from is not None:
            filters["expense_date"] = [">=", date_from]
        elif date_to is not None:
            filters["expense_date"] = ["<=", date_to]

        return frappe.get_all(
            "Expense",
            filters=filters,
            fields=[
                "name",
                "category",
                "amount",
                "expense_date",
                "dependent",
                "description",
                "source",
                "payment_method",
                "creation",
                "modified",
            ],
            order_by="expense_date desc, creation desc",
            limit_page_length=limit or 0,
        )

    @staticmethod
    def get_recent_expenses(
        owner_user: str,
        dependent: Optional[str | list] = None,
        limit: int = 10,
    ) -> list[dict]:
        return ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            limit=limit,
        )

    @staticmethod
    def attach_dependent_names(
        rows: list[dict],
        owner_user: str,
    ) -> list[dict]:
        """Resolve the current dependent_name for every row that references a
        dependent, so displayed names always reflect the dependent's latest
        rename instead of a value captured at expense creation time."""
        ids = {row.get("dependent") for row in rows if row.get("dependent")}
        names: dict[str, str] = {}
        if ids:
            dep_rows = frappe.get_all(
                "Dependent",
                filters={"name": ["in", list(ids)], "guardian": owner_user},
                fields=["name", "dependent_name"],
            )
            names = {dep["name"]: dep["dependent_name"] for dep in dep_rows}
        for row in rows:
            row["dependent_name"] = names.get(row.get("dependent"), "")
        return rows

    @staticmethod
    def get_expenses_by_category(
        owner_user: str,
        category: str,
        dependent: Optional[str] = None,
    ) -> list[dict]:
        return ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            category=category,
        )

    @staticmethod
    def get_expenses_by_date_range(
        owner_user: str,
        date_from: str | date,
        date_to: str | date,
        dependent: Optional[str] = None,
    ) -> list[dict]:
        return ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            date_from=date_from,
            date_to=date_to,
        )

    @staticmethod
    def _create_doc(fields: dict) -> Document:
        doc = frappe.get_doc(
            {
                "doctype": "Expense",
                **fields,
            },
            ignore_permissions=True,
        )
        doc.insert(ignore_permissions=True)
        return doc

    @staticmethod
    def _get_expense(
        owner_user: str,
        expense: str,
    ) -> Document:
        try:
            doc = frappe.get_doc("Expense", expense, ignore_permissions=True)

        except frappe.DoesNotExistError as exc:
            raise ExpenseNotFoundError(
                _("Expense not found.")
            ) from exc

        if doc.owner_user != owner_user:
            raise ExpenseNotFoundError(
                _("Expense not found.")
            )

        return doc

    @staticmethod
    def _validate_category(
        owner_user: str,
        category: str,
        dependent: Optional[str] = None,
    ) -> None:
        # Categories are a shared, guardian-owned pool. The dependent
        # argument is kept for signature symmetry; the per-dependent
        # allowed-categories check lives in _validate_dependent_category
        # below.
        CategoryService.get_category(owner_user, category)

    @staticmethod
    def _validate_dependent(
        owner_user: str,
        dependent: Optional[str],
    ) -> None:
        if dependent is not None:
            DependentService.get_dependent(owner_user, dependent)

    @staticmethod
    def _validate_dependent_category(
        owner_user: str,
        category: str,
        dependent: Optional[str],
    ) -> None:
        """Enforce the dependent's allowed-categories list.

        Mirrors the Telegram bot's check so the REST path cannot bypass it:
        a dependent expense may only use a category the guardian has
        explicitly allowed. An empty allowed list means "all active
        guardian categories" — handled by DependentService.list_allowed_categories.
        """
        if dependent is None:
            return

        category_id = CategoryService.get_category(owner_user, category).name

        allowed_ids = {
            row["name"]
            for row in DependentService.list_allowed_categories(
                owner_user, dependent, active_only=True
            )
        }

        if category_id not in allowed_ids:
            raise CategoryNotAllowedError(
                _("This category is not allowed for this dependent.")
            )

    @staticmethod
    def _validate_amount(amount: float) -> float:
        if amount is None:
            raise InvalidExpenseAmountError(
                _("Expense amount is required.")
            )

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidExpenseAmountError(
                _("Expense amount must be numeric.")
            )

        if amount <= 0:
            raise InvalidExpenseAmountError(
                _("Expense amount must be greater than zero.")
            )

        return round(flt(amount), 2)

    @staticmethod
    def _validate_expense_date(expense_date: str | date) -> None:
        if expense_date is None:
            raise InvalidExpenseDateError(
                _("Expense date is required.")
            )

        try:
            parsed_date = frappe.utils.getdate(expense_date)
        except Exception as exc:
            raise InvalidExpenseDateError(
                _("Expense date is invalid.")
            ) from exc

        today = frappe.utils.getdate(frappe.utils.today())

        if parsed_date > today:
            raise InvalidExpenseDateError(
                _("Expense date cannot be in the future.")
            )

    @staticmethod
    def _validate_source(source: str) -> None:
        valid_sources = {item.value for item in ExpenseSource}

        if source not in valid_sources:
            raise InvalidExpenseSourceError(
                _("Invalid expense source '{0}'.").format(source)
            )