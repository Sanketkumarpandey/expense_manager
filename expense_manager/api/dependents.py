"""Whitelisted Dependent endpoints. Thin wrappers only — every rule
lives in DependentService. Scoped to frappe.session.user (the
guardian) — dependents themselves have no desk/REST access, only
Telegram."""

import frappe
from frappe.utils import cint, flt

from expense_manager.services.dependent_service import DependentService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.api.utils import current_user as _current_user

# Same rationale as api/budgets.py: DependentService.update_dependent
# distinguishes "field not supplied" from "field explicitly cleared"
# for telegram_username/telegram_user_id via its own private _UNSET.
# This local sentinel preserves that without importing the private one.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_dependent(
    dependent_name,
    relationship,
    default_monthly_allowance,
    telegram_username=None,
    telegram_user_id=None,
    allow_carry_forward=1,
):
    user = _current_user()
    try:
        return DependentService.create_dependent(
            user,
            dependent_name,
            relationship,
            flt(default_monthly_allowance),
            telegram_username=telegram_username,
            telegram_user_id=telegram_user_id,
            allow_carry_forward=bool(cint(allow_carry_forward)),
        ).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_dependent(dependent):
    user = _current_user()
    try:
        return DependentService.get_dependent(user, dependent).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_dependent(
    dependent,
    dependent_name=None,
    relationship=None,
    default_monthly_allowance=None,
    telegram_username=_API_UNSET,
    telegram_user_id=_API_UNSET,
    allow_carry_forward=None,
):
    user = _current_user()

    kwargs = {}
    if dependent_name is not None:
        kwargs["dependent_name"] = dependent_name
    if relationship is not None:
        kwargs["relationship"] = relationship
    if default_monthly_allowance is not None:
        kwargs["default_monthly_allowance"] = flt(default_monthly_allowance)
    if telegram_username is not _API_UNSET:
        kwargs["telegram_username"] = telegram_username or None
    if telegram_user_id is not _API_UNSET:
        kwargs["telegram_user_id"] = telegram_user_id or None
    if allow_carry_forward is not None:
        kwargs["allow_carry_forward"] = bool(cint(allow_carry_forward))

    try:
        return DependentService.update_dependent(user, dependent, **kwargs).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_dependent(dependent):
    user = _current_user()
    try:
        DependentService.delete_dependent(user, dependent)
        return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_dependent(dependent):
    user = _current_user()
    try:
        return DependentService.archive_dependent(user, dependent).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_dependent(dependent):
    user = _current_user()
    try:
        return DependentService.restore_dependent(user, dependent).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_dependents(active_only=0):
    user = _current_user()
    try:
        return DependentService.list_dependents(user, active_only=bool(cint(active_only)))
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_dependents(search_text=None, active_only=1):
    user = _current_user()
    try:
        return DependentService.search_dependents(
            user,
            search_text,
            active_only=bool(cint(active_only)),
        )
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}