"""Whitelisted Expense endpoints. Thin wrappers only — every rule
lives in ExpenseService. Scoped to frappe.session.user (the guardian).
The Telegram voice pipeline creates expenses through TelegramService,
not through this file — this is the desk/REST path only."""

import frappe
from frappe.utils import cint, flt

from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.api.utils import current_user as _current_user

# Same rationale as api/budgets.py and api/dependents.py:
# ExpenseService.update_expense distinguishes "not supplied" from
# "explicitly cleared" for dependent/description/payment_method via
# its own private _UNSET. This local sentinel preserves that.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_expense(
    category,
    amount,
    expense_date,
    dependent=None,
    description=None,
    source=None,
    payment_method=None,
    voice_transcript=None,
):
    user = _current_user()

    kwargs = {}
    if source is not None:
        kwargs["source"] = source

    try:
        return ExpenseService.create_expense(
            user,
            category,
            flt(amount),
            expense_date,
            dependent=dependent,
            description=description,
            payment_method=payment_method,
            voice_transcript=voice_transcript,
            **kwargs,
        ).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expense(expense):
    user = _current_user()
    try:
        return ExpenseService.get_expense(user, expense).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_expense(
    expense,
    category=None,
    amount=None,
    expense_date=None,
    dependent=_API_UNSET,
    description=_API_UNSET,
    payment_method=_API_UNSET,
):
    user = _current_user()

    kwargs = {}
    if category is not None:
        kwargs["category"] = category
    if amount is not None:
        kwargs["amount"] = flt(amount)
    if expense_date is not None:
        kwargs["expense_date"] = expense_date
    if dependent is not _API_UNSET:
        kwargs["dependent"] = dependent or None
    if description is not _API_UNSET:
        kwargs["description"] = description or None
    if payment_method is not _API_UNSET:
        kwargs["payment_method"] = payment_method or None

    try:
        return ExpenseService.update_expense(user, expense, **kwargs).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_expense(expense):
    user = _current_user()
    try:
        ExpenseService.delete_expense(user, expense)
        return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_expenses(dependent=None, category=None, date_from=None, date_to=None, limit=None):
    user = _current_user()
    try:
        return ExpenseService.list_expenses(
            user,
            dependent=dependent,
            category=category,
            date_from=date_from,
            date_to=date_to,
            limit=cint(limit) if limit else None,
        )
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_recent_expenses(dependent=None, limit=10):
    user = _current_user()
    try:
        return ExpenseService.get_recent_expenses(user, dependent=dependent, limit=cint(limit))
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expenses_by_category(category, dependent=None):
    user = _current_user()
    try:
        return ExpenseService.get_expenses_by_category(user, category, dependent=dependent)
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expenses_by_date_range(date_from, date_to, dependent=None):
    user = _current_user()
    try:
        return ExpenseService.get_expenses_by_date_range(
            user,
            date_from,
            date_to,
            dependent=dependent,
        )
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}