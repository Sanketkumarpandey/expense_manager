from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.utils import flt, getdate, today, get_first_day, add_months, get_last_day

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
            include_all=True,
        )

        category_names = ReportService._category_name_lookup(owner_user)

        summary = []

        for budget in active_budgets:
            usage = BudgetService.get_budget_usage(
	            owner_user, budget["category"],
                dependent=budget.get("dependent"),
	            include_all=True,
	        )

            if usage is None:
                continue

            cat_info = category_names.get(budget["category"], {})
            summary.append(
                {
                    "category": budget["category"],
                    "category_name": cat_info.get("category_name", budget["category"]),
                    "category_icon": cat_info.get("icon", ""),
                    "allocated_amount": usage["allocated_amount"],
                    "spent_amount": usage["spent_amount"],
                    "remaining_amount": usage["remaining_amount"],
                    "percentage": usage["pct_used"],
                    "is_overspent": usage["is_overspent"],
				}
	        )

        return sorted(summary, key=lambda row: row["spent_amount"], reverse=True)

    @staticmethod
    def get_pocket_money_summary(
        owner_user: str,
        dependent: Optional[str] = None,
    ) -> list[dict]:
        active_dependents = DependentService.list_dependents(owner_user, active_only=True)

        if dependent is not None:
            active_dependents = [
                row for row in active_dependents if row["name"] == dependent
            ]

        summary = []

        for dep_row in active_dependents:
            balance = PocketMoneyService.get_balance(owner_user, dep_row["name"])

            if balance is None:
                # No active allocation for this dependent right now —
                # nothing to report, not an error.
                continue

            # total_savings = the rollover savings ledger PLUS the current
            # allocation's unspent remainder. This is the "allocation − spent"
            # figure users read as savings (and it stays correct after a
            # rollover, where the unspent balance is banked into the ledger).
            total_savings = flt(balance.get("total_savings", 0)) + flt(
                balance["remaining_amount"]
            )

            summary.append(
                {
                    "dependent": dep_row["name"],
                    "dependent_name": dep_row["dependent_name"],
                    "allocated_amount": balance["allocated_amount"],
                    "spent_amount": balance["spent_amount"],
                    "carry_forward": balance["carry_forward"],
                    "remaining_amount": balance["remaining_amount"],
                    "total_savings": total_savings,
                }
            )

        return summary

    @staticmethod
    def get_category_breakdown(
        owner_user: str,
        dependent: Optional[str] = None,
        date_from=None,
        date_to=None,
        category: Optional[str] = None,
    ) -> list[dict]:
        ReportService._validate_date_range(date_from, date_to)

        expenses = ReportService._get_expenses(
            owner_user,
            dependent=dependent,
            date_from=date_from,
            date_to=date_to,
            category=category,
        )
        grouped = ReportService._group_by_category(expenses)
        category_names = ReportService._category_name_lookup(owner_user)

        total_amount = sum(row["total_amount"] for row in grouped.values())

        breakdown = []

        for category, row in grouped.items():
            cat_info = category_names.get(category, {})
            breakdown.append(
                {
                    "category": category,
                    "category_name": cat_info.get("category_name", category),
                    "category_icon": cat_info.get("icon", ""),
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
        category: Optional[str] = None,
    ) -> list[dict]:
        if months <= 0:
            raise InvalidReportDateRangeError(
                _("Number of months must be greater than zero.")
            )

        date_to = getdate(today())
        date_from = get_first_day(add_months(date_to, -(months - 1)))

        expenses = ReportService._get_expenses(
            owner_user,
            dependent=dependent,
            date_from=date_from,
            date_to=date_to,
            category=category,
        )
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
    def get_dashboard_summary(
        owner_user: str,
        dependent: Optional[str] = None,
        category: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        return ReportService._build_dashboard(
            owner_user,
            dependent=dependent,
            category=category,
            date_from=date_from,
            date_to=date_to,
        )

    # ------------------------------------------------------------------
    # New: Expense Detail Report (with budget info per row)
    # ------------------------------------------------------------------

    @staticmethod
    def get_expense_detail_report(
        owner_user: str,
        from_date=None,
        to_date=None,
        individual: Optional[str] = None,
        dependent: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        ReportService._validate_date_range(from_date, to_date)

        lookup_user = ReportService._resolve_report_user(owner_user, individual)

        expenses = ExpenseService.list_expenses(
            lookup_user,
            dependent=dependent,
            category=category,
            date_from=from_date,
            date_to=to_date,
        )

        category_names = ReportService._category_name_lookup(lookup_user)
        budget_data = {}
        active_budgets = BudgetService.list_budgets(lookup_user, active_only=True)
        for b in active_budgets:
            usage = BudgetService.get_budget_usage(lookup_user, b["category"])
            if usage:
                budget_data[b["category"]] = usage

        rows = []
        for exp in expenses:
            cat = exp["category"]
            cat_info = category_names.get(cat, {})
            budget_info = budget_data.get(cat, {})
            allocated = budget_info.get("allocated_amount", 0)
            spent = budget_info.get("spent_amount", 0)
            remaining = budget_info.get("remaining_amount", 0)
            is_overspent = budget_info.get("is_overspent", False)

            if allocated:
                status = _("Over Budget") if is_overspent else _("Within Budget")
            else:
                status = _("No Budget")

            dependent_name = ""
            if exp.get("dependent"):
                dep_name = frappe.db.get_value("Dependent", exp["dependent"], "dependent_name")
                if dep_name:
                    dependent_name = dep_name

            rows.append({
                "expense_date": exp["expense_date"],
                "description": exp.get("description", ""),
                "category_name": cat_info.get("category_name", cat),
                "category_icon": cat_info.get("icon", ""),
                "individual": exp["owner_user"],
                "dependent": dependent_name,
                "amount": flt(exp["amount"]),
                "budget": flt(allocated),
                "remaining_budget": flt(remaining),
                "status": status,
                "category": cat,
            })

        return rows

    # ------------------------------------------------------------------
    # New: Pocket Money Detail Report
    # ------------------------------------------------------------------

    @staticmethod
    def get_pocket_money_detail_report(
        owner_user: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        dependent: Optional[str] = None,
    ) -> list[dict]:
        from datetime import date
        today_date = getdate(today())
        month = month or today_date.month
        year = year or today_date.year

        dep_list = DependentService.list_dependents(owner_user, active_only=True)
        if dependent:
            dep_list = [d for d in dep_list if d["name"] == dependent]

        period_start = getdate(f"{year}-{month:02d}-01")
        period_end = get_last_day(period_start)

        rows = []
        for dep in dep_list:
            balance = PocketMoneyService.get_balance(owner_user, dep["name"])
            if balance is None:
                continue

            period_expenses = ExpenseService.list_expenses(
                owner_user,
                dependent=dep["name"],
                date_from=period_start,
                date_to=period_end,
            )
            total_spent = flt(sum(flt(e["amount"]) for e in period_expenses))

            remaining = flt(balance["remaining_amount"])
            savings = flt(balance.get("total_savings", 0))

            rows.append({
                "dependent_name": dep["dependent_name"],
                "allocated_amount": flt(balance["allocated_amount"]),
                "total_expenses": total_spent,
                "remaining_amount": remaining,
                "savings": savings,
                "carry_forward": flt(balance["carry_forward"]),
            })

        return rows

    # ------------------------------------------------------------------
    # New: Guardian Overview Report
    # ------------------------------------------------------------------

    @staticmethod
    def get_guardian_overview_data(
        owner_user: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        requested_user: Optional[str] = None,
    ) -> list[dict]:
        from datetime import date
        today_date = getdate(today())
        month = month or today_date.month
        year = year or today_date.year

        period_start = getdate(f"{year}-{month:02d}-01")
        period_end = get_last_day(period_start)

        guardian = ReportService._resolve_report_user(owner_user, requested_user)
        dep_list = DependentService.list_dependents(guardian, active_only=True)

        rows = []
        for dep in dep_list:
            balance = PocketMoneyService.get_balance(guardian, dep["name"])

            period_expenses = ExpenseService.list_expenses(
                guardian,
                dependent=dep["name"],
                date_from=period_start,
                date_to=period_end,
            )
            total_spent = flt(sum(flt(e["amount"]) for e in period_expenses))

            allocation_amount = flt(balance["allocated_amount"]) if balance else 0
            remaining = flt(balance["remaining_amount"]) if balance else 0
            savings = flt(balance.get("total_savings", 0)) if balance else 0

            rows.append({
                "dependent_name": dep["dependent_name"],
                "allocation": allocation_amount,
                "expenses": total_spent,
                "remaining": remaining,
                "savings": savings,
            })

        return rows

    # ------------------------------------------------------------------
    # New: Category Analytics Report
    # ------------------------------------------------------------------

    @staticmethod
    def get_category_analytics_data(
        owner_user: str,
        month: Optional[int] = None,
        year: Optional[int] = None,
        individual: Optional[str] = None,
        category: Optional[str] = None,
    ) -> list[dict]:
        from datetime import date
        today_date = getdate(today())
        month = month or today_date.month
        year = year or today_date.year

        period_start = getdate(f"{year}-{month:02d}-01")
        period_end = get_last_day(period_start)

        target_user = ReportService._resolve_report_user(owner_user, individual)

        breakdown = ReportService.get_category_breakdown(
            target_user,
            date_from=period_start,
            date_to=period_end,
        )

        if category:
            breakdown = [r for r in breakdown if r["category"] == category]

        budget_data = {}
        active_budgets = BudgetService.list_budgets(target_user, active_only=True)
        for b in active_budgets:
            usage = BudgetService.get_budget_usage(target_user, b["category"])
            if usage:
                budget_data[b["category"]] = usage

        rows = []
        for row in breakdown:
            cat = row["category"]
            budget_info = budget_data.get(cat, {})
            budget_amount = flt(budget_info.get("allocated_amount", 0))
            expenses_amount = flt(row["total_amount"])
            remaining = max(0, budget_amount - expenses_amount) if budget_amount else 0
            usage_pct = round((expenses_amount / budget_amount) * 100, 2) if budget_amount else 0

            rows.append({
                "category_name": row["category_name"],
                "budget": budget_amount,
                "expenses": expenses_amount,
                "remaining": remaining,
                "usage_pct": usage_pct,
            })

        return rows

    # ------------------------------------------------------------------
    # New: Monthly Expense Trend Report
    # ------------------------------------------------------------------

    @staticmethod
    def get_monthly_expense_trend_data(
        owner_user: str,
        year: Optional[int] = None,
        individual: Optional[str] = None,
    ) -> dict:
        year = year or getdate(today()).year
        target_user = ReportService._resolve_report_user(owner_user, individual)

        monthly_data = ReportService.get_monthly_report(target_user, year=year)

        amounts = [row["total_amount"] for row in monthly_data]
        non_zero = [a for a in amounts if a > 0]

        highest = max(amounts) if amounts else 0
        lowest = min(non_zero) if non_zero else 0
        average = flt(sum(amounts) / len(amounts)) if amounts else 0

        highest_month = ""
        lowest_month = ""
        for row in monthly_data:
            if row["total_amount"] == highest:
                highest_month = row["month"]
            if row["total_amount"] == lowest and row["total_amount"] > 0:
                lowest_month = row["month"]

        return {
            "monthly_data": monthly_data,
            "highest_month": highest_month,
            "highest_amount": highest,
            "lowest_month": lowest_month,
            "lowest_amount": lowest,
            "average_monthly": average,
        }

    # ------------------------------------------------------------------
    # Notification message builders (called by jobs/reminders.py)
    # ------------------------------------------------------------------

    @staticmethod
    def build_no_expenses_today_message(owner_user: str) -> str | None:
        """Return a nudge reminder if the user has not logged any expenses today."""
        expenses = ReportService._get_expenses(
            owner_user, date_from=today(), date_to=today()
        )
        if expenses:
            return None
        return "You haven't logged any expenses today. Send /help to see how to add one."

    @staticmethod
    def build_weekly_summary_message(owner_user: str) -> str | None:
        """Return a weekly spending summary, or None if no expenses this week."""
        from frappe.utils import add_days

        date_to = getdate(today())
        date_from = add_days(date_to, -6)

        breakdown = ReportService.get_category_breakdown(
            owner_user, date_from=date_from, date_to=date_to
        )
        if not breakdown:
            return None

        total = sum(row["total_amount"] for row in breakdown)
        lines = [f"Weekly summary ({date_from} to {date_to}):"]
        for row in breakdown[:5]:
            lines.append(f"  {row['category_name']}: {row['total_amount']}")
        lines.append(f"  Total: {total}")
        return "\n".join(lines)

    @staticmethod
    def build_monthly_summary_message(owner_user: str) -> str | None:
        """Return a monthly spending summary, or None if no expenses this month."""
        month_start = get_first_day(today())

        breakdown = ReportService.get_category_breakdown(
            owner_user, date_from=month_start, date_to=today()
        )
        if not breakdown:
            return None

        total = sum(row["total_amount"] for row in breakdown)
        lines = [f"Monthly summary ({month_start} to {today()}):"]
        for row in breakdown[:5]:
            lines.append(f"  {row['category_name']}: {row['total_amount']}")
        lines.append(f"  Total: {total}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_dashboard(
        owner_user: str,
        dependent: Optional[str] = None,
        category: Optional[str] = None,
        date_from=None,
        date_to=None,
    ) -> dict:
        month_start = get_first_day(today())

        total_expense = ReportService._calculate_totals(
            ReportService._get_expenses(
                owner_user,
                dependent=dependent,
                category=category,
                date_from=date_from,
                date_to=date_to,
            )
        )["total_amount"]

        monthly_expense = ReportService._calculate_totals(
            ReportService._get_expenses(
                owner_user,
                dependent=dependent,
                category=category,
                date_from=month_start,
                date_to=today(),
            )
        )["total_amount"]

        budget_summary = ReportService.get_budget_summary(owner_user, category=category)

        recent = ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            category=category,
            date_from=date_from,
            date_to=date_to,
            limit=6,
        )
        category_names = ReportService._category_name_lookup(owner_user)
        for row in recent:
            cat_info = category_names.get(row.get("category"), {})
            row["category_name"] = cat_info.get("category_name", row.get("category", ""))
            row["category_icon"] = cat_info.get("icon", "")
        ExpenseService.attach_dependent_names(recent, owner_user)

        return {
            "total_expense": total_expense,
            "monthly_expense": monthly_expense,
            "active_budgets": len(budget_summary),
            "over_budget": sum(1 for row in budget_summary if row["is_overspent"]),
            "dependents": len(DependentService.list_dependents(owner_user, active_only=True)),
            "remaining_budget": sum(row["remaining_amount"] for row in budget_summary),
            "recent_expenses": recent,
            "overspent": [row for row in budget_summary if row["is_overspent"]],
        }

    @staticmethod
    def _get_expenses(
        owner_user: str,
        dependent: Optional[str] = None,
        date_from=None,
        date_to=None,
        category: Optional[str] = None,
    ) -> list[dict]:
        return ExpenseService.list_expenses(
            owner_user,
            dependent=dependent,
            category=category,
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
        categories = frappe.get_all(
            "Category",
            filters={"owner_user": owner_user},
            fields=["name", "category_name", "icon"],
        )
        return {
            row["name"]: {
                "category_name": row["category_name"],
                "icon": row.get("icon", "") or "",
            }
            for row in categories
        }

    @staticmethod
    def _validate_date_range(date_from, date_to) -> None:
        if date_from is None or date_to is None:
            return

        if getdate(date_to) < getdate(date_from):
            raise InvalidReportDateRangeError(
                _("End date cannot be before start date.")
            )

    @staticmethod
    def _resolve_report_user(
        owner_user: str,
        requested_user: Optional[str] = None,
    ) -> str:
        """Resolve the identity a report is scoped to.

        Reports run inside the viewer's session, so the safe default is
        the session user. A client-supplied ``requested_user``
        (``individual``/``guardian`` filter) must never change who the
        report reads for a normal user — it is honored only when the
        current session belongs to System Manager / Administrator
        (cross-guardian reporting).
        """
        session_user = frappe.session.user

        if requested_user and requested_user != owner_user:
            roles = frappe.get_roles(session_user)
            if session_user == "Administrator" or "System Manager" in roles:
                return requested_user

        return owner_user
