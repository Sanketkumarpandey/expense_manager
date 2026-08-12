from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	filters = filters or {}
	owner_user = frappe.session.user

	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	individual = filters.get("individual")
	dependent = filters.get("dependent")
	category = filters.get("category")

	rows = ReportService.get_expense_detail_report(
		owner_user,
		from_date=from_date,
		to_date=to_date,
		individual=individual,
		dependent=dependent,
		category=category,
	)

	columns = [
		{"fieldname": "expense_date", "label": _("Date"), "fieldtype": "Date", "width": 100},
		{"fieldname": "description", "label": _("Expense"), "fieldtype": "Data", "width": 180},
		{"fieldname": "category_name", "label": _("Category"), "fieldtype": "Data", "width": 120},
		{"fieldname": "individual", "label": _("Individual"), "fieldtype": "Data", "width": 120},
		{"fieldname": "dependent", "label": _("Dependent"), "fieldtype": "Data", "width": 120},
		{"fieldname": "amount", "label": _("Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "budget", "label": _("Budget"), "fieldtype": "Currency", "width": 120},
		{
			"fieldname": "remaining_budget",
			"label": _("Remaining Budget"),
			"fieldtype": "Currency",
			"width": 130,
		},
		{"fieldname": "status", "label": _("Status"), "fieldtype": "Data", "width": 120},
	]

	total_amount = flt(sum(row["amount"] for row in rows))
	total_budget = flt(sum(row["budget"] for row in rows))
	remaining = flt(sum(row["remaining_budget"] for row in rows))
	overspent = len(set(row["category"] for row in rows if row["status"] == _("Over Budget")))
	expense_count = len(rows)

	report_summary = [
		{"label": _("Total Expenses"), "value": total_amount, "datatype": "Currency", "currency": "INR"},
		{"label": _("Total Budget"), "value": total_budget, "datatype": "Currency", "currency": "INR"},
		{"label": _("Remaining Budget"), "value": remaining, "datatype": "Currency", "currency": "INR"},
		{"label": _("Overspent Categories"), "value": overspent, "datatype": "Int"},
		{"label": _("Number of Expenses"), "value": expense_count, "datatype": "Int"},
	]

	chart = _build_chart(owner_user, from_date, to_date, dependent)

	return columns, rows, None, chart, report_summary


def _build_chart(owner_user, from_date, to_date, dependent):
	category_breakdown = ReportService.get_category_breakdown(
		owner_user,
		dependent=dependent,
		date_from=from_date,
		date_to=to_date,
	)

	labels = [r["category_name"] for r in category_breakdown]
	values = [r["total_amount"] for r in category_breakdown]

	return {
		"data": {
			"labels": labels,
			"datasets": [{"name": _("Amount"), "values": values}],
		},
		"type": "pie",
		"fieldtype": "Currency",
	}
