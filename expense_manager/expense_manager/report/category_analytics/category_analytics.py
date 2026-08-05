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
    individual = filters.get("individual")
    category = filters.get("category")

    if month:
        month = int(month)
    if not year:
        year = getdate(today()).year

    rows = ReportService.get_category_analytics_data(
        owner_user,
        month=month,
        year=year,
        individual=individual,
        category=category,
    )

    columns = [
        {"fieldname": "category_name", "label": _("Category"), "fieldtype": "Data", "width": 150},
        {"fieldname": "budget", "label": _("Budget"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "expenses", "label": _("Expenses"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "remaining", "label": _("Remaining"), "fieldtype": "Currency", "width": 120},
        {"fieldname": "usage_pct", "label": _("Usage %"), "fieldtype": "Percent", "width": 100},
    ]

    chart = _build_chart(rows)

    return columns, rows, None, chart, None


def _build_chart(rows):
    labels = [r["category_name"] for r in rows]
    expense_values = [r["expenses"] for r in rows]

    return {
        "data": {
            "labels": labels,
            "datasets": [{"name": _("Expenses"), "values": expense_values}],
        },
        "type": "pie",
        "fieldtype": "Currency",
    }
