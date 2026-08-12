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
	dependent = filters.get("dependent")

	if month:
		month = int(month)
	if not year:
		year = getdate(today()).year

	rows = ReportService.get_pocket_money_detail_report(
		owner_user,
		month=month,
		year=year,
		dependent=dependent,
	)

	columns = [
		{"fieldname": "dependent_name", "label": _("Dependent"), "fieldtype": "Data", "width": 150},
		{
			"fieldname": "allocated_amount",
			"label": _("Pocket Money Allocated"),
			"fieldtype": "Currency",
			"width": 150,
		},
		{"fieldname": "total_expenses", "label": _("Total Expenses"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "remaining_amount", "label": _("Remaining"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "savings", "label": _("Savings"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "carry_forward", "label": _("Carry Forward"), "fieldtype": "Currency", "width": 120},
	]

	total_allocation = flt(sum(r["allocated_amount"] for r in rows))
	total_spent = flt(sum(r["total_expenses"] for r in rows))
	total_remaining = flt(sum(r["remaining_amount"] for r in rows))
	total_savings = flt(sum(r["savings"] for r in rows))

	report_summary = [
		{
			"label": _("Total Allocation"),
			"value": total_allocation,
			"datatype": "Currency",
			"currency": "INR",
		},
		{"label": _("Total Spent"), "value": total_spent, "datatype": "Currency", "currency": "INR"},
		{"label": _("Total Remaining"), "value": total_remaining, "datatype": "Currency", "currency": "INR"},
		{"label": _("Total Savings"), "value": total_savings, "datatype": "Currency", "currency": "INR"},
	]

	chart = _build_chart(rows)

	return columns, rows, None, chart, report_summary


def _build_chart(rows):
	labels = [r["dependent_name"] for r in rows]
	allocated_values = [r["allocated_amount"] for r in rows]
	spent_values = [r["total_expenses"] for r in rows]

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": _("Allocated"), "values": allocated_values},
				{"name": _("Spent"), "values": spent_values},
			],
		},
		"type": "bar",
		"fieldtype": "Currency",
	}
