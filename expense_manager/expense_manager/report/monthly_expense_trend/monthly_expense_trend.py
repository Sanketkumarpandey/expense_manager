from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate, today

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	filters = filters or {}
	owner_user = frappe.session.user

	year = filters.get("year")
	individual = filters.get("individual")

	if not year:
		year = getdate(today()).year

	data = ReportService.get_monthly_expense_trend_data(
		owner_user,
		year=year,
		individual=individual,
	)

	monthly_data = data["monthly_data"]

	columns = [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 120},
		{"fieldname": "total_amount", "label": _("Total Amount"), "fieldtype": "Currency", "width": 150},
	]

	rows = [{"month": r["month"], "total_amount": r["total_amount"]} for r in monthly_data]

	highest_month = data["highest_month"] or "-"
	lowest_month = data["lowest_month"] or "-"

	report_summary = [
		{"label": _("Highest Spending Month"), "value": highest_month, "datatype": "Data"},
		{"label": _("Amount"), "value": data["highest_amount"], "datatype": "Currency", "currency": "INR"},
		{"label": _("Lowest Spending Month"), "value": lowest_month, "datatype": "Data"},
		{"label": _("Amount"), "value": data["lowest_amount"], "datatype": "Currency", "currency": "INR"},
		{
			"label": _("Average Monthly Expense"),
			"value": data["average_monthly"],
			"datatype": "Currency",
			"currency": "INR",
		},
	]

	chart = _build_chart(monthly_data)

	return columns, rows, None, chart, report_summary


def _build_chart(monthly_data):
	labels = [r["month"] for r in monthly_data]
	values = [r["total_amount"] for r in monthly_data]

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Monthly Spending"), "values": values}],
		},
		"type": "line",
		"fieldtype": "Currency",
	}
