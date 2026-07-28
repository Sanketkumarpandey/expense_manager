# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	filters = filters or {}
	year = filters.get("year")

	owner_user = frappe.session.user
	data = ReportService.get_monthly_report(owner_user, year=year)

	columns = [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 120},
		{"fieldname": "total_amount", "label": _("Total Amount"), "fieldtype": "Currency", "width": 150},
	]

	rows = [{"month": row["month"], "total_amount": row["total_amount"]} for row in data]

	return columns, rows
