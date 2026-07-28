"""Whitelisted Budget endpoints. Thin wrappers only — every rule
lives in BudgetService. Scoped to frappe.session.user (the guardian)."""

import frappe
from frappe.utils import cint, flt

from expense_manager.services.budget_service import BudgetService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.api.utils import current_user as _current_user

# BudgetService.update_budget distinguishes "notes not supplied" (leave
# untouched) from "notes explicitly cleared" (set to null) via its own
# private _UNSET sentinel. This local sentinel lets the REST layer
# preserve that distinction without reaching into a private object
# from another module: if the client omits `notes` entirely, we never
# pass the kwarg at all, so BudgetService's own default applies.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_budget(
    category,
    allocated_amount,
    period,
    start_date,
    end_date,
    alert_threshold_pct=90,
    notes=None,
):
    user = _current_user()
    try:
        return BudgetService.create_budget(
            user,
            category,
            flt(allocated_amount),
            period,
            start_date,
            end_date,
            alert_threshold_pct=cint(alert_threshold_pct),
            notes=notes,
        ).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_budget(budget):
    user = _current_user()
    try:
        return BudgetService.get_budget(user, budget).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_budget(
    budget,
    allocated_amount=None,
    period=None,
    start_date=None,
    end_date=None,
    alert_threshold_pct=None,
    notes=_API_UNSET,
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

    try:
        return BudgetService.update_budget(user, budget, **kwargs).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_budget(budget):
    user = _current_user()
    try:
        BudgetService.delete_budget(user, budget)
        return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_budget(budget):
    user = _current_user()
    try:
        return BudgetService.archive_budget(user, budget).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_budget(budget):
    user = _current_user()
    try:
        return BudgetService.restore_budget(user, budget).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_budgets(category=None, active_only=0):
    user = _current_user()
    try:
        return BudgetService.list_budgets(
            user,
            category=category,
            active_only=bool(cint(active_only)),
        )
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_budgets(search_text=None, active_only=1):
    user = _current_user()
    try:
        return BudgetService.search_budgets(
            user,
            search_text,
            active_only=bool(cint(active_only)),
        )
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_budget_usage(category):
    user = _current_user()
    try:
        usage = BudgetService.get_budget_usage(user, category)
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}

    if usage is None:
        return {"success": False, "message": "No active budget for this category."}
    return usage