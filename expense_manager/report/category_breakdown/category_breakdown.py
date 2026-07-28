# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	filters = filters or {}
	dependent = filters.get("dependent")
	date_from = filters.get("date_from")
	date_to = filters.get("date_to")

	owner_user = frappe.session.user
	data = ReportService.get_category_breakdown(
		owner_user, dependent=dependent, date_from=date_from, date_to=date_to
	)

	columns = [
		{"fieldname": "category_name", "label": _("Category"), "fieldtype": "Data", "width": 150},
		{"fieldname": "total_amount", "label": _("Total Amount"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "expense_count", "label": _("Expenses"), "fieldtype": "Int", "width": 100},
		{"fieldname": "percentage_of_total", "label": ("% of Total"), "fieldtype": "Percent", "width": 120},
	]

	rows = [
		{
			"category_name": row["category_name"],
			"total_amount": row["total_amount"],
			"expense_count": row["expense_count"],
			"percentage_of_total": row["percentage_of_total"],
		}
		for row in data
	]

	return columns, rows
