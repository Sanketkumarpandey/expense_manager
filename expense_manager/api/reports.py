"""Whitelisted report endpoints, including chart image rendering.

generate_chart_png() is a plain helper, not a whitelisted endpoint —
it's imported directly by telegram/handlers/report.py to build a PNG
before calling Telegram's sendPhoto. Everything below it is the
REST-facing side: read-only wrappers around ReportService, scoped to
frappe.session.user (the guardian). A guardian's reports already
include their dependents' data, since Expense rows share the
guardian's owner_user regardless of which dependent they're for.
"""

import io

import matplotlib

matplotlib.use("Agg")
import frappe
import matplotlib.pyplot as plt
from frappe.utils import cint

from expense_manager.api.utils import current_user as _current_user
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.report_service import ReportService


def generate_chart_png(
	dataset: list[dict],
	title: str = "",
	x_key: str = "label",
	y_key: str = "value",
) -> bytes:
	labels = [str(row.get(x_key, "")) for row in dataset]
	values = [row.get(y_key, 0) for row in dataset]

	fig, ax = plt.subplots(figsize=(6, 4))
	ax.bar(labels, values, color="#4C72B0")
	ax.set_title(title)
	ax.set_ylabel("Amount")
	plt.xticks(rotation=30, ha="right")
	fig.tight_layout()

	buffer = io.BytesIO()
	fig.savefig(buffer, format="png")
	plt.close(fig)
	buffer.seek(0)
	return buffer.getvalue()


# ----------------------------------------------------------------------
# Whitelisted REST endpoints — read-only wrappers around ReportService
# ----------------------------------------------------------------------


@frappe.whitelist(methods=["GET"])
def get_expense_summary(dependent=None, date_from=None, date_to=None):
	user = _current_user()
	try:
		return ReportService.get_expense_summary(
			user,
			dependent=dependent,
			date_from=date_from,
			date_to=date_to,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_budget_summary(category=None):
	user = _current_user()
	try:
		return ReportService.get_budget_summary(user, category=category)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_pocket_money_summary(dependent=None):
	user = _current_user()
	try:
		return ReportService.get_pocket_money_summary(user, dependent=dependent)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_category_breakdown(dependent=None, date_from=None, date_to=None, category=None):
	user = _current_user()
	try:
		return ReportService.get_category_breakdown(
			user,
			dependent=dependent,
			date_from=date_from,
			date_to=date_to,
			category=category,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_monthly_report(dependent=None, year=None):
	user = _current_user()
	try:
		return ReportService.get_monthly_report(
			user,
			dependent=dependent,
			year=cint(year) if year else None,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_dependent_report(dependent):
	user = _current_user()
	try:
		return ReportService.get_dependent_report(user, dependent)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_spending_trend(dependent=None, months=6, category=None):
	user = _current_user()
	try:
		return ReportService.get_spending_trend(
			user,
			dependent=dependent,
			months=cint(months),
			category=category,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_dashboard_summary(dependent=None, category=None, date_from=None, date_to=None):
	user = _current_user()
	try:
		return ReportService.get_dashboard_summary(
			user,
			dependent=dependent,
			category=category,
			date_from=date_from,
			date_to=date_to,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}
