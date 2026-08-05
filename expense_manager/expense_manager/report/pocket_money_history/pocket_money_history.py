# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from expense_manager.services.report_service import ReportService


def execute(filters=None):
	owner_user = frappe.session.user
	data = ReportService.get_pocket_money_summary(owner_user)

	columns = [
		{"fieldname": "dependent_name", "label": _("Dependent"), "fieldtype": "Data", "width": 150},
		{"fieldname": "allocated_amount", "label": _("Allocated"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "spent_amount", "label": _("Spent"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "carry_forward", "label": _("Carry Forward"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "remaining_amount", "label": _("Remaining"), "fieldtype": "Currency", "width": 120},
	]

	rows = [
		{
			"dependent_name": row["dependent_name"],
			"allocated_amount": row["allocated_amount"],
			"spent_amount": row["spent_amount"],
			"carry_forward": row["carry_forward"],
			"remaining_amount": row["remaining_amount"],
		}
		for row in data
	]

	return columns, rows
