"""Whitelisted Budget endpoints. Thin wrappers only — every rule
lives in BudgetService. Scoped to frappe.session.user (the guardian)."""

import frappe
from frappe.utils import cint, flt

from expense_manager.api.utils import current_user as _current_user
from expense_manager.api.utils import resolve_category_id
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.exceptions import ExpenseManagerError

# BudgetService.update_budget distinguishes "notes not supplied" (leave
# untouched) from "notes explicitly cleared" (set to null) via its own
# private _UNSET sentinel. This local sentinel lets the REST layer
# preserve that distinction without reaching into a private object
# from another module: if the client omits `notes` entirely, we never
# pass the kwarg at all, so BudgetService's own default applies.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_budget(
	category: str,
	allocated_amount: float,
	period: str = "Monthly",
	start_date: str | None = None,
	end_date: str | None = None,
	alert_threshold_pct: int = 90,
	notes: str | None = None,
	dependent: str | None = None,
):
	user = _current_user()
	if not start_date:
		start_date = frappe.utils.today()
	if not end_date:
		end_date = frappe.utils.get_last_day(start_date)
	dependent = dependent or None
	try:
		resolved_category = resolve_category_id(user, category)
		return BudgetService.create_budget(
			user,
			resolved_category,
			flt(allocated_amount),
			period,
			start_date,
			end_date,
			alert_threshold_pct=cint(alert_threshold_pct),
			notes=notes,
			dependent=dependent,
		).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_budget(budget: str, dependent: str | None = None):
	user = _current_user()
	try:
		return BudgetService.get_budget(user, budget, dependent=dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_budget(
	budget: str,
	allocated_amount: float | None = None,
	period: str | None = None,
	start_date: str | None = None,
	end_date: str | None = None,
	alert_threshold_pct: int | None = None,
	notes: str | None = _API_UNSET,
	dependent: str | None = None,
):
	user = _current_user()

	kwargs = {}
	if allocated_amount is not None:
		kwargs["allocated_amount"] = flt(allocated_amount)
	if period is not None:
		kwargs["period"] = period
	if start_date is not None:
		kwargs["start_date"] = start_date
	if end_date is not None:
		kwargs["end_date"] = end_date
	if alert_threshold_pct is not None:
		kwargs["alert_threshold_pct"] = cint(alert_threshold_pct)
	if notes is not _API_UNSET:
		kwargs["notes"] = notes or None
	if dependent is not None:
		kwargs["dependent"] = dependent

	try:
		return BudgetService.update_budget(user, budget, **kwargs).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_budget(budget: str, dependent: str | None = None):
	user = _current_user()
	try:
		BudgetService.delete_budget(user, budget, dependent=dependent)
		return {"success": True}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_budget(budget: str, dependent: str | None = None):
	user = _current_user()
	try:
		return BudgetService.archive_budget(user, budget, dependent=dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_budget(budget: str, dependent: str | None = None):
	user = _current_user()
	try:
		return BudgetService.restore_budget(user, budget, dependent=dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_budgets(category: str | None = None, active_only: int = 0, dependent: str | None = None):
	user = _current_user()
	dependent = dependent or None
	try:
		resolved_category = resolve_category_id(user, category) if category else None
		return BudgetService.list_budgets(
			user,
			category=resolved_category,
			active_only=bool(cint(active_only)),
			dependent=dependent,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_budgets(search_text: str | None = None, active_only: int = 1, dependent: str | None = None):
	user = _current_user()
	dependent = dependent or None
	try:
		return BudgetService.search_budgets(
			user,
			search_text,
			active_only=bool(cint(active_only)),
			dependent=dependent,
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_budget_usage(category: str, dependent: str | None = None):
	user = _current_user()
	dependent = dependent or None
	try:
		resolved_category = resolve_category_id(user, category)
		usage = BudgetService.get_budget_usage(user, resolved_category, dependent=dependent)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}

	if usage is None:
		return {"success": False, "message": "No active budget for this category."}
	return usage
