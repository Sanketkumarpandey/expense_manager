# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from expense_manager.services.report_service import ReportService


def _empty_result():
	columns = [
		{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 200},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 200},
	]
	rows = [{"metric": _("Please select a dependent to view the report."), "value": ""}]
	return columns, rows


def execute(filters=None):
	filters = filters or {}
	dependent = filters.get("dependent")

	if not dependent:
		return _empty_result()

	owner_user = frappe.session.user
	data = ReportService.get_dependent_report(owner_user, dependent)

	columns = [
		{"fieldname": "metric", "label": _("Metric"), "fieldtype": "Data", "width": 200},
		{"fieldname": "value", "label": _("Value"), "fieldtype": "Data", "width": 200},
	]

	pocket_money = data.get("pocket_money") or {}
	expense_summary = data.get("expense_summary") or {}

	rows = [
		{"metric": _("Dependent Name"), "value": data.get("dependent_name", "")},
		{"metric": _("Total Expenses"), "value": expense_summary.get("total_amount", 0)},
		{"metric": _("Expense Count"), "value": expense_summary.get("expense_count", 0)},
		{"metric": _("Average Expense"), "value": expense_summary.get("average_expense", 0)},
		{"metric": _("Pocket Money Allocated"), "value": pocket_money.get("allocated_amount", 0)},
		{"metric": _("Pocket Money Spent"), "value": pocket_money.get("spent_amount", 0)},
		{"metric": _("Pocket Money Remaining"), "value": pocket_money.get("remaining_amount", 0)},
	]

	category_breakdown = data.get("category_breakdown") or []
	if category_breakdown:
		rows.append({"metric": "", "value": ""})
		rows.append({"metric": _("--- Category Breakdown ---"), "value": ""})
		for cat in category_breakdown:
			rows.append(
				{
					"metric": "  " + cat.get("category_name", ""),
					"value": cat.get("total_amount", 0),
				}
			)

	return columns, rows
