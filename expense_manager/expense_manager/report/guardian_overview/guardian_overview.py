from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from expense_manager.services.report_service import ReportService


def execute(filters=None):
    filters = filters or {}
    owner_user = frappe.session.user

    month = filters.get("month")
    year = filters.get("year")
    requested_guardian = filters.get("guardian")

    if month:
        month = int(month)
    if not year:
        year = getdate(today()).year

    rows = ReportService.get_guardian_overview_data(
        owner_user,
        month=month,
        year=year,
        requested_user=requested_guardian,
    )

    columns = [
        {"fieldname": "dependent_name", "label": _("Dependent"), "fieldtype": "Data", "width": 150},
        {"fieldname": "allocation", "label": _("Allocation"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "expenses", "label": _("Expenses"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "remaining", "label": _("Remaining"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "savings", "label": _("Savings"), "fieldtype": "Currency", "width": 120},
    ]

    total_dependents = len(rows)
    total_expenses = flt(sum(r["expenses"] for r in rows))
    total_allocation = flt(sum(r["allocation"] for r in rows))
    total_savings = flt(sum(r["savings"] for r in rows))
    avg_spending = flt(total_expenses / total_dependents) if total_dependents else 0

    report_summary = [
        {"label": _("Total Dependents"), "value": total_dependents, "datatype": "Int"},
        {"label": _("Total Expenses"), "value": total_expenses, "datatype": "Currency", "currency": "INR"},
        {"label": _("Total Allocation"), "value": total_allocation, "datatype": "Currency", "currency": "INR"},
        {"label": _("Total Savings"), "value": total_savings, "datatype": "Currency", "currency": "INR"},
        {"label": _("Average Spending"), "value": avg_spending, "datatype": "Currency", "currency": "INR"},
    ]

    chart = _build_chart(rows)

    return columns, rows, None, chart, report_summary


def _build_chart(rows):
    labels = [r["dependent_name"] for r in rows]
    expenses = [r["expenses"] for r in rows]
    allocations = [r["allocation"] for r in rows]

    return {
        "data": {
            "labels": labels,
            "datasets": [
                {"name": _("Allocation"), "values": allocations},
                {"name": _("Expenses"), "values": expenses},
            ],
        },
        "type": "bar",
        "fieldtype": "Currency",
    }
