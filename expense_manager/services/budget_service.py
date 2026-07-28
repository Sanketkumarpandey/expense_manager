from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt
from frappe.utils import getdate

from expense_manager.services.exceptions import (
    BudgetAlreadyExistsError,
    BudgetNotFoundError,
    InvalidBudgetPeriodError,
    InvalidBudgetAmountError,
    InvalidBudgetDateRangeError,
    InvalidAlertThresholdError,
)
from expense_manager.services.category_service import CategoryService
from expense_manager.constants.budget import BudgetPeriod
from expense_manager.utils.logger import logger
from expense_manager.utils.helpers import escape_like


_UNSET = object()


class BudgetService:

    @staticmethod
    def create_budget(
        owner_user: str,
        category: str,
        allocated_amount: float,
        period: str,
        start_date,
        end_date,
        alert_threshold_pct: int = 90,
        notes: Optional[str] = None,
    ) -> Document:
        BudgetService._validate_category(owner_user, category)
        BudgetService._validate_period(period)
        allocated_amount = BudgetService._validate_amount(allocated_amount)
        BudgetService._validate_dates(start_date, end_date)
        alert_threshold_pct = BudgetService._validate_threshold(alert_threshold_pct)

        if BudgetService._get_active_budget_for_category(owner_user, category) is not None:
            raise BudgetAlreadyExistsError(
                _("An active budget already exists for this category.")
            )

        budget = frappe.get_doc(
            {
                "doctype": "Budget",
                "owner_user": owner_user,
                "category": category,
                "allocated_amount": allocated_amount,
                "spent_amount": 0,
                "period": period,
                "start_date": start_date,
                "end_date": end_date,
                "alert_threshold_pct": alert_threshold_pct,
                "notes": notes,
                "is_active": 1,
            },
            ignore_permissions=True,
        )

        budget.insert(ignore_permissions=True)

        BudgetService.refresh_budget(owner_user, category)

        logger.info(
            "Budget created | owner=%s | category=%s | id=%s | allocated=%s",
            owner_user,
            category,
            budget.name,
            allocated_amount,
        )

        return budget

    @staticmethod
    def get_budget(
        owner_user: str,
        budget: str,
    ) -> Document:
        return BudgetService._get_budget(owner_user, budget)

    @staticmethod
    def update_budget(
        owner_user: str,
        budget: str,
        allocated_amount: Optional[float] = None,
        period: Optional[str] = None,
        start_date=None,
        end_date=None,
        alert_threshold_pct: Optional[int] = None,
        notes: str | None | object = _UNSET,
    ) -> Document:
        doc = BudgetService._get_budget(owner_user, budget)

        if allocated_amount is not None:
            doc.allocated_amount = BudgetService._validate_amount(allocated_amount)

        if period is not None:
            BudgetService._validate_period(period)
            doc.period = period

        if start_date is not None or end_date is not None:
            new_start = start_date if start_date is not None else doc.start_date
            new_end = end_date if end_date is not None else doc.end_date
            BudgetService._validate_dates(new_start, new_end)
            doc.start_date = new_start
            doc.end_date = new_end

        if alert_threshold_pct is not None:
            doc.alert_threshold_pct = BudgetService._validate_threshold(alert_threshold_pct)

        if notes is not _UNSET:
            doc.notes = notes

        doc.save(ignore_permissions=True)

        BudgetService.refresh_budget(owner_user, doc.category)

        logger.info(
            "Budget updated | owner=%s | id=%s",
            owner_user,
            doc.name,
        )

        return doc

    @staticmethod
    def delete_budget(
        owner_user: str,
        budget: str,
    ) -> None:
        doc = BudgetService._get_budget(owner_user, budget)

        doc.delete(ignore_permissions=True)

        logger.info(
            "Budget deleted | owner=%s | id=%s",
            owner_user,
            doc.name,
        )

    @staticmethod
    def archive_budget(
        owner_user: str,
        budget: str,
    ) -> Document:
        return BudgetService._set_active_status(owner_user, budget, False)

    @staticmethod
    def restore_budget(
        owner_user: str,
        budget: str,
    ) -> Document:
        return BudgetService._set_active_status(owner_user, budget, True)

    @staticmethod
    def list_budgets(
        owner_user: str,
        category: Optional[str] = None,
        active_only: bool = False,
    ) -> list[dict]:
        filters = {
            "owner_user": owner_user,
        }

        if category is not None:
            filters["category"] = category

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Budget",
            filters=filters,
            fields=[
                "name",
                "category",
                "allocated_amount",
                "spent_amount",
                "period",
                "start_date",
                "end_date",
                "alert_threshold_pct",
                "is_active",
                "creation",
                "modified",
            ],
            order_by="category asc",
        )

    @staticmethod
    def search_budgets(
        owner_user: str,
        search_text: Optional[str],
        active_only: bool = True,
    ) -> list[dict]:
        if not search_text:
            return []

        filters = {
            "owner_user": owner_user,
            "notes": ["like", f"%{escape_like(search_text.strip())}%"],
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Budget",
            filters=filters,
            fields=[
                "name",
                "category",
                "allocated_amount",
                "spent_amount",
            ],
            order_by="category asc",
        )

    @staticmethod
    def get_budget_usage(
        owner_user: str,
        category: str,
    ) -> Optional[dict]:
        budget = BudgetService._get_active_budget_for_category(owner_user, category)

        if budget is None:
            return None

        remaining = budget.allocated_amount - budget.spent_amount
        pct_used = (
            (budget.spent_amount / budget.allocated_amount) * 100
            if budget.allocated_amount
            else 0
        )

        return {
            "budget": budget.name,
            "allocated_amount": budget.allocated_amount,
            "spent_amount": budget.spent_amount,
            "remaining_amount": remaining,
            "pct_used": round(pct_used, 2),
            "is_overspent": budget.spent_amount > budget.allocated_amount,
        }

    @staticmethod
    def refresh_budget(
        owner_user: str,
        category: str,
    ) -> None:
        budget = BudgetService._get_active_budget_for_category(owner_user, category)

        if budget is None:
            return

        spent_amount = BudgetService._calculate_spent_amount(
            owner_user,
            category,
            budget.start_date,
            budget.end_date,
        )

        budget.spent_amount = spent_amount
        budget.save(ignore_permissions=True)

        BudgetService._check_overspend(budget)

        logger.info(
            "Budget refreshed | owner=%s | category=%s | id=%s | spent=%s",
            owner_user,
            category,
            budget.name,
            spent_amount,
        )

    @staticmethod
    def _get_budget(
        owner_user: str,
        budget: str,
    ) -> Document:
        try:
            doc = frappe.get_doc("Budget", budget, ignore_permissions=True)

        except frappe.DoesNotExistError as exc:
            raise BudgetNotFoundError(
                _("Budget not found.")
            ) from exc

        if doc.owner_user != owner_user:
            raise BudgetNotFoundError(
                _("Budget not found.")
            )

        return doc

    @staticmethod
    def _get_active_budget_for_category(
        owner_user: str,
        category: str,
    ) -> Optional[Document]:
        name = frappe.db.get_value(
            "Budget",
            {
                "owner_user": owner_user,
                "category": category,
                "is_active": 1,
            },
            "name",
        )

        if not name:
            return None

        return frappe.get_doc("Budget", name, ignore_permissions=True)

    @staticmethod
    def _calculate_spent_amount(
        owner_user: str,
        category: str,
        start_date,
        end_date,
    ) -> float:
        total = frappe.db.get_value(
            "Expense",
            {
                "owner_user": owner_user,
                "category": category,
                "expense_date": ["between", [start_date, end_date]],
            },
            "sum(amount)",
        )

        return flt(total)

    @staticmethod
    def _check_overspend(budget: Document) -> None:
        if budget.allocated_amount <= 0:
            return

        if budget.spent_amount > budget.allocated_amount:
            logger.info(
                "Budget exceeded | owner=%s | category=%s | id=%s | spent=%s | allocated=%s",
                budget.owner_user,
                budget.category,
                budget.name,
                budget.spent_amount,
                budget.allocated_amount,
            )
            return

        pct_used = (budget.spent_amount / budget.allocated_amount) * 100

        if pct_used >= budget.alert_threshold_pct:
            logger.info(
                "Budget threshold reached | owner=%s | category=%s | id=%s | pct=%s",
                budget.owner_user,
                budget.category,
                budget.name,
                round(pct_used, 1),
            )

    @staticmethod
    def _set_active_status(
        owner_user: str,
        budget: str,
        is_active: bool,
    ) -> Document:
        doc = BudgetService._get_budget(owner_user, budget)

        if doc.is_active == is_active:
            return doc

        doc.is_active = is_active
        doc.save(ignore_permissions=True)

        logger.info(
            "Budget %s | owner=%s | id=%s",
            "restored" if is_active else "archived",
            owner_user,
            doc.name,
        )

        return doc

    @staticmethod
    def _validate_category(
        owner_user: str,
        category: str,
    ) -> None:
        CategoryService.get_category(owner_user, category)

    @staticmethod
    def _validate_period(period: str) -> None:
        valid_periods = {item.value for item in BudgetPeriod}

        if period not in valid_periods:
            raise InvalidBudgetPeriodError(
                _("Invalid budget period '{0}'.").format(period)
            )

    @staticmethod
    def _validate_amount(amount: float) -> float:
        if amount is None:
            raise InvalidBudgetAmountError(
                _("Allocated amount is required.")
            )

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidBudgetAmountError(
                _("Allocated amount must be numeric.")
            )

        if amount <= 0:
            raise InvalidBudgetAmountError(
                _("Allocated amount must be greater than zero.")
            )

        return amount

    @staticmethod
    def _validate_dates(start_date, end_date) -> None:
        start = frappe.utils.getdate(start_date)
        end = frappe.utils.getdate(end_date)

        if end < start:
            raise InvalidBudgetDateRangeError(
                _("End date cannot be before start date.")
            )

    @staticmethod
    def _validate_threshold(pct: int) -> int:
        try:
            pct = int(pct)
        except (TypeError, ValueError):
            raise InvalidAlertThresholdError(
                _("Alert threshold must be a whole number.")
            )

        if pct < 0 or pct > 100:
            raise InvalidAlertThresholdError(
                _("Alert threshold must be between 0 and 100.")
            )

        return pct

    @staticmethod
    def list_all_active_budgets() -> list[dict]:
        """
        System-level only — bypasses per-user ownership scoping.
        Never call this from a handler or API method; only from a
        scheduled job that has no single acting user.
        """
        return frappe.get_all(
            "Budget",
            filters={"is_active": 1},
            fields=["name", "owner_user", "category", "alert_threshold_pct"],
        )

    @staticmethod
    def build_budget_alert_message(category_name: str, usage: dict) -> str:
        label = "over budget" if usage["is_overspent"] else "close to your budget"
        return (
            f"\u26a0\ufe0f You're {label} in {category_name}: {usage['spent_amount']} spent of "
            f"{usage['allocated_amount']} allocated ({usage['pct_used']}%)."
        )

    @staticmethod
    def can_send_budget_alert(owner_user: str, budget: str) -> bool:
        doc = BudgetService._get_budget(owner_user, budget)

        if not doc.last_alert_sent_on:
            return True

        return getdate(doc.last_alert_sent_on) != getdate(frappe.utils.today())

    @staticmethod
    def mark_budget_alert_sent(owner_user: str, budget: str) -> None:
        doc = BudgetService._get_budget(owner_user, budget)
        doc.last_alert_sent_on = frappe.utils.today()
        doc.save(ignore_permissions=True)

    @staticmethod
    def try_claim_budget_alert(owner_user: str, budget: str) -> bool:
        """Atomically check if an alert can be sent today and mark it as sent.

        Returns True if the alert was claimed (caller should send it),
        False if already sent today or budget not found.
        """
        doc = BudgetService._get_budget(owner_user, budget)

        if doc.last_alert_sent_on and getdate(doc.last_alert_sent_on) == getdate(frappe.utils.today()):
            return False

        doc.last_alert_sent_on = frappe.utils.today()
        doc.save(ignore_permissions=True)
        return True