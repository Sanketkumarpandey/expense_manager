from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, get_first_day, add_months

from expense_manager.services.exceptions import InvalidReportDateRangeError
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.expense_service import ExpenseService


class ReportService:
    """
    Read-only. Composes data already produced by ExpenseService,
    BudgetService, PocketMoneyService, DependentService and
    CategoryService — never recalculates a number that one of those
    already owns (remaining budget, pocket money balance, etc).

    Never creates, updates, or deletes anything. Direct aggregation
    (grouping expenses by category or month) is done here in Python
    over already-fetched rows, since that's presentation logic, not
    a business rule.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def get_expense_summary(
        owner_user: str,
        dependent: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        ReportService._validate_date_range(date_from, date_to)

        expenses = ReportService._get_expenses(owner_user, dependent, date_from, date_to)
        totals = ReportService._calculate_totals(expenses)

        return {
            "total_amount": totals["total_amount"],
            "expense_count": totals["expense_count"],
            "average_expense": totals["average_expense"],
            "date_from": date_from,
            "date_to": date_to,
        }

    @staticmethod
    def get_budget_summary(
        owner_user: str,
        category: Optional[str] = None,
    ) -> list[dict]:
        active_budgets = BudgetService.list_budgets(
            owner_user,
            category=category,
            active_only=True,
        )

        category_names = ReportService._category_name_lookup(owner_user)

        summary = []

        for budget in active_budgets:
            usage = BudgetService.get_budget_usage(owner_user, budget["category"])

            if usage is None:
                continue

            summary.append(
                {
                    "category": budget["category"],
                    "category_name": category_names.get(budget["category"], budget["category"]),
                    "allocated_amount": usage["allocated_amount"],
                    "spent_amount": usage["spent_amount"],
                    "remaining_amount": usage["remaining_amount"],
                    "percentage": usage["pct_used"],
                    "is_overspent": usage["is_overspent"],
                }
            )

        return sorted(summary, key=lambda row: row["spent_amount"], reverse=True)

    @staticmethod
    def get_pocket_money_summary(owner_user: str) -> list[dict]:
        active_dependents = DependentService.list_dependents(owner_user, active_only=True)

        summary = []

        for dependent in active_dependents:
            balance = PocketMoneyService.get_balance(owner_user, dependent["name"])

            if balance is None:
                # No active allocation for this dependent right now —
                # nothing to report, not an error.
                continue

            summary.append(
                {
                    "dependent": dependent["name"],
                    "dependent_name": dependent["dependent_name"],
                    "allocated_amount": balance["allocated_amount"],
                    "spent_amount": balance["spent_amount"],
                    "carry_forward": balance["carry_forward"],
                    "remaining_amount": balance["remaining_amount"],
                }
            )

        return summary

    @staticmethod
    def get_category_breakdown(
        owner_user: str,
        dependent: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> list[dict]:
        ReportService._validate_date_range(date_from, date_to)

        expenses = ReportService._get_expenses(owner_user, dependent, date_from, date_to)
        grouped = ReportService._group_by_category(expenses)
        category_names = ReportService._category_name_lookup(owner_user)

        total_amount = sum(row["total_amount"] for row in grouped.values())

        breakdown = []

        for category, row in grouped.items():
            breakdown.append(
                {
                    "category": category,
                    "category_name": category_names.get(category, category),
                    "total_amount": row["total_amount"],
                    "expense_count": row["expense_count"],
                    "percentage_of_total": (
                        round((row["total_amount"] / total_amount) * 100, 2)
                        if total_amount
                        else 0
                    ),
                }
            )

        return sorted(breakdown, key=lambda row: row["total_amount"], reverse=True)

    @staticmethod
    def get_monthly_report(
        owner_user: str,
        dependent: Optional[str] = None,
        year: Optional[int] = None,
    ) -> list[dict]:
        year = year or getdate(today()).year

        date_from = getdate(f"{year}-01-01")
        date_to = getdate(f"{year}-12-31")

        expenses = ReportService._get_expenses(owner_user, dependent, date_from, date_to)
        grouped = ReportService._group_by_month(expenses)

        return [
            {
                "month": f"{year}-{month:02d}",
                "total_amount": grouped.get(f"{year}-{month:02d}", 0),
            }
            for month in range(1, 13)
        ]

    @staticmethod
    def get_dependent_report(
        owner_user: str,
        dependent: str,
    ) -> dict:
        dependent_doc = DependentService.get_dependent(owner_user, dependent)

        return {
            "dependent": dependent_doc.name,
            "dependent_name": dependent_doc.dependent_name,
            "pocket_money": PocketMoneyService.get_balance(owner_user, dependent),
            "expense_summary": ReportService.get_expense_summary(
                owner_user,
                dependent=dependent,
            ),
            "category_breakdown": ReportService.get_category_breakdown(
                owner_user,
                dependent=dependent,
            ),
        }

    @staticmethod
    def get_spending_trend(
        owner_user: str,
        dependent: Optional[str] = None,
        months: int = 6,
    ) -> list[dict]:
        if months <= 0:
            raise InvalidReportDateRangeError(
                _("Number of months must be greater than zero.")
            )

        date_to = getdate(today())
        date_from = get_first_day(add_months(date_to, -(months - 1)))

        expenses = ReportService._get_expenses(owner_user, dependent, date_from, date_to)
        grouped = ReportService._group_by_month(expenses)

        ordered_keys = []
        cursor = getdate(get_first_day(date_from))

        for _i in range(months):
            ordered_keys.append(cursor.strftime("%Y-%m"))
            cursor = add_months(cursor, 1)

        return [
            {"month": key, "total_amount": grouped.get(key, 0)}
            for key in ordered_keys
        ]

    @staticmethod
    def get_dashboard_summary(owner_user: str) -> dict:
        return ReportService._build_dashboard(owner_user)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dashboard(owner_user: str) -> dict:
        month_start = get_first_day(today())

        total_expense = ReportService._calculate_totals(
            ReportService._get_expenses(owner_user)
        )["total_amount"]

        monthly_expense = ReportService._calculate_totals(
            ReportService._get_expenses(owner_user, date_from=month_start, date_to=today())
        )["total_amount"]

        budget_summary = ReportService.get_budget_summary(owner_user)

        return {
            "total_expense": total_expense,
            "monthly_expense": monthly_expense,
            "active_budgets": len(budget_summary),
            "over_budget": sum(1 for row in budget_summary if row["is_overspent"]),
            "dependents": len(DependentService.list_dependents(owner_user, active_only=True)),
            "remaining_budget": sum(row["remaining_amount"] for row in budget_summary),
        }

    @staticmethod
    def _get_expenses(
        owner_user: str,
        dependent: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> list[dict]:
        return ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            date_from=date_from,
            date_to=date_to,
        )

    @staticmethod
    def _group_by_category(expenses: list[dict]) -> dict:
        grouped: dict = {}

        for expense in expenses:
            category = expense["category"]
            row = grouped.setdefault(category, {"total_amount": 0, "expense_count": 0})
            row["total_amount"] = flt(row["total_amount"] + flt(expense["amount"]))
            row["expense_count"] += 1

        return grouped

    @staticmethod
    def _group_by_month(expenses: list[dict]) -> dict:
        grouped: dict = {}

        for expense in expenses:
            month_key = getdate(expense["expense_date"]).strftime("%Y-%m")
            grouped[month_key] = flt(grouped.get(month_key, 0) + flt(expense["amount"]))

        return grouped

    @staticmethod
    def _calculate_totals(expenses: list[dict]) -> dict:
        total_amount = flt(sum(flt(expense["amount"]) for expense in expenses))
        expense_count = len(expenses)
        average_expense = flt(total_amount / expense_count) if expense_count else 0

        return {
            "total_amount": total_amount,
            "expense_count": expense_count,
            "average_expense": average_expense,
        }

    @staticmethod
    def _category_name_lookup(owner_user: str) -> dict:
        categories = CategoryService.list_categories(owner_user)
        return {row["name"]: row["category_name"] for row in categories}

    @staticmethod
    def _validate_date_range(date_from, date_to) -> None:
        if date_from is None or date_to is None:
            return

        if getdate(date_to) < getdate(date_from):
            raise InvalidReportDateRangeError(
                _("End date cannot be before start date.")
            )