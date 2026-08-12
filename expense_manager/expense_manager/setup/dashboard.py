"""Creates Dashboard Charts, Number Cards, and Workspace for Expense Manager.

Called from hooks.py via after_migrate.
"""

import frappe
from frappe import _


def after_migrate():
	"""Run after every migrate to ensure dashboard components exist."""
	_create_dashboard_charts()
	_create_number_cards()
	_create_workspace()


def _create_dashboard_charts():
	charts = [
		{
			"chart_name": "Expense Trend",
			"chart_type": "Report",
			"report_name": "Monthly Expense Trend",
			"type": "Line",
			"is_public": 1,
			"filters_json": "{}",
		},
		{
			"chart_name": "Category Spending",
			"chart_type": "Report",
			"report_name": "Category Analytics",
			"type": "Pie",
			"is_public": 1,
			"filters_json": "{}",
		},
		{
			"chart_name": "Pocket Money Utilization",
			"chart_type": "Report",
			"report_name": "Pocket Money Summary",
			"type": "Bar",
			"is_public": 1,
			"filters_json": "{}",
		},
		{
			"chart_name": "Savings Growth",
			"chart_type": "Report",
			"report_name": "Monthly Expense Trend",
			"type": "Line",
			"is_public": 1,
			"filters_json": "{}",
		},
		{
			"chart_name": "Budget Utilization",
			"chart_type": "Report",
			"report_name": "Expense Summary",
			"type": "Bar",
			"is_public": 1,
			"filters_json": "{}",
		},
	]

	for chart_data in charts:
		name = chart_data["chart_name"]
		if frappe.db.exists("Dashboard Chart", name):
			continue
		doc = frappe.get_doc({"doctype": "Dashboard Chart", **chart_data})
		doc.insert(ignore_permissions=True)

	frappe.logger("expense_manager").info("setup/dashboard: dashboard charts created")


def _create_number_cards():
	cards = [
		{
			"label": "Total Expenses",
			"document_type": "Expense",
			"function": "Sum",
			"aggregate_function_based_on": "amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Monthly Expenses",
			"document_type": "Expense",
			"function": "Sum",
			"aggregate_function_based_on": "amount",
			"show_percentage_stats": 1,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Total Savings",
			"document_type": "Pocket Money Allocation",
			"function": "Sum",
			"aggregate_function_based_on": "carry_forward_amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Remaining Pocket Money",
			"document_type": "Pocket Money Allocation",
			"function": "Sum",
			"aggregate_function_based_on": "total_available_amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Total Dependents",
			"document_type": "Dependent",
			"function": "Count",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Overspent Categories",
			"document_type": "Budget",
			"function": "Sum",
			"aggregate_function_based_on": "spent_amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Monthly Budget",
			"document_type": "Budget",
			"function": "Sum",
			"aggregate_function_based_on": "allocated_amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
		{
			"label": "Budget Remaining",
			"document_type": "Budget",
			"function": "Sum",
			"aggregate_function_based_on": "spent_amount",
			"show_percentage_stats": 0,
			"stats_time_interval": "Monthly",
			"type": "Document Type",
			"is_public": 1,
		},
	]

	for card_data in cards:
		name = card_data["label"]
		if frappe.db.exists("Number Card", name):
			continue
		doc = frappe.get_doc({"doctype": "Number Card", **card_data})
		doc.insert(ignore_permissions=True)

	frappe.logger("expense_manager").info("setup/dashboard: number cards created")


def _create_workspace():
	"""Create or update the Expense Manager workspace."""
	workspace_name = "Expense Manager"

	if frappe.db.exists("Workspace", workspace_name):
		return

	doc = frappe.get_doc(
		{
			"doctype": "Workspace",
			"title": workspace_name,
			"module": "Expense Manager",
			"icon": "assets/expense_manager/icons/expense.png",
			"is_default": 1,
			"label": workspace_name,
			"app": "expense_manager",
			"chart_links": [
				{
					"label": "Expense Trend",
					"chart_name": "Expense Trend",
					"width": "Medium",
				},
				{
					"label": "Category Spending",
					"chart_name": "Category Spending",
					"width": "Medium",
				},
				{
					"label": "Budget Utilization",
					"chart_name": "Budget Utilization",
					"width": "Medium",
				},
				{
					"label": "Savings Growth",
					"chart_name": "Savings Growth",
					"width": "Medium",
				},
			],
			"number_cards": [
				{"label": "Total Expenses", "number_card_name": "Total Expenses", "width": "Medium"},
				{"label": "Total Savings", "number_card_name": "Total Savings", "width": "Medium"},
				{
					"label": "Remaining Pocket Money",
					"number_card_name": "Remaining Pocket Money",
					"width": "Medium",
				},
				{
					"label": "Budget Remaining",
					"number_card_name": "Budget Remaining",
					"width": "Medium",
				},
			],
			"links": [
				{
					"label": "Expense Summary",
					"type": "Link",
					"link_to": "Expense Summary",
					"link_type": "Report",
					"dependencies": "Expense",
				},
				{
					"label": "Pocket Money Summary",
					"type": "Link",
					"link_to": "Pocket Money Summary",
					"link_type": "Report",
					"dependencies": "Pocket Money Allocation",
				},
				{
					"label": "Guardian Overview",
					"type": "Link",
					"link_to": "Guardian Overview",
					"link_type": "Report",
					"dependencies": "Dependent",
				},
				{
					"label": "Category Analytics",
					"type": "Link",
					"link_to": "Category Analytics",
					"link_type": "Report",
					"dependencies": "Expense",
				},
				{
					"label": "Monthly Expense Trend",
					"type": "Link",
					"link_to": "Monthly Expense Trend",
					"link_type": "Report",
					"dependencies": "Expense",
				},
			],
			"shortcuts": [
				{
					"label": _("New Expense"),
					"type": "DocType",
					"link_to": "Expense",
					"format": "List",
				},
				{
					"label": _("New Pocket Money Allocation"),
					"type": "DocType",
					"link_to": "Pocket Money Allocation",
					"format": "List",
				},
				{
					"label": _("New Category"),
					"type": "DocType",
					"link_to": "Category",
					"format": "List",
				},
				{
					"label": _("New Dependent"),
					"type": "DocType",
					"link_to": "Dependent",
					"format": "List",
				},
			],
		},
		ignore_permissions=True,
	)

	doc.insert(ignore_permissions=True)
	frappe.logger("expense_manager").info("setup/dashboard: workspace created")
