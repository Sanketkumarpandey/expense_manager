# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	filters = filters or {}
	category = filters.get("category")

	owner_user = frappe.session.user
	data = ReportService.get_budget_summary(owner_user, category=category)

	columns = [
		{"fieldname": "category_name", "label": _("Category"), "fieldtype": "Data", "width": 150},
		{"fieldname": "allocated_amount", "label": _("Allocated"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "spent_amount", "label": _("Spent"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "remaining_amount", "label": _("Remaining"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "percentage", "label": _("Utilization %"), "fieldtype": "Percent", "width": 120},
		{"fieldname": "is_overspent", "label": _("Over Budget"), "fieldtype": "Check", "width": 100},
	]

	rows = [
		{
			"category_name": row["category_name"],
			"allocated_amount": row["allocated_amount"],
			"spent_amount": row["spent_amount"],
			"remaining_amount": row["remaining_amount"],
			"percentage": row["percentage"],
			"is_overspent": row["is_overspent"],
		}
		for row in data
	]

	return columns, rows
