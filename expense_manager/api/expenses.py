"""Whitelisted Expense endpoints. Thin wrappers only — every rule
lives in ExpenseService. Scoped to frappe.session.user (the guardian).
The Telegram voice pipeline creates expenses through TelegramService,
not through this file — this is the desk/REST path only."""

import frappe
from frappe.utils import cint, flt

from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.ai_service import AIService
from expense_manager.ai.exceptions import AIError
from expense_manager.config.exceptions import ConfigurationError
from expense_manager.constants.expense import ExpenseSource
from expense_manager.api.utils import current_user as _current_user
from expense_manager.api.utils import resolve_category_id

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
        resolved_category = resolve_category_id(user, category)
        doc = ExpenseService.create_expense(
            user,
            resolved_category,
            flt(amount),
            expense_date,
            dependent=dependent,
            description=description,
            payment_method=payment_method,
            voice_transcript=voice_transcript,
            **kwargs,
        ).as_dict()
        lookup = _category_lookup(user)
        response = _enrich_expense(doc, lookup)
        warning = BudgetService.build_inline_overspend_warning(
            user, doc.get("category"), dependent=doc.get("dependent")
        )
        if warning:
            response["warning"] = warning
        return response
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expense(expense):
    user = _current_user()
    try:
        doc = ExpenseService.get_expense(user, expense).as_dict()
        lookup = _category_lookup(user)
        return _enrich_expense(doc, lookup)
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
        doc = ExpenseService.update_expense(user, expense, **kwargs).as_dict()
        lookup = _category_lookup(user)
        return _enrich_expense(doc, lookup)
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def create_expense_from_text(text, dependent=None):
    """AI-assisted quick add. Thin wrapper around AIService so the desk
    quick-add box and the Telegram text pipeline share the same parsing
    logic. Mirrors TelegramService.create_expense_from_text error handling:
    unconfigured AI keys surface a friendly config message instead of an
    internal traceback."""
    user = _current_user()
    try:
        expense = AIService.create_expense_from_text(
            owner_user=user,
            text=text,
            dependent=dependent,
            source=ExpenseSource.WEB,
        )
        doc = expense.as_dict()
        lookup = _category_lookup(user)
        response = _enrich_expense(doc, lookup)
        warning = BudgetService.build_inline_overspend_warning(
            user, doc.get("category"), dependent=doc.get("dependent")
        )
        if warning:
            response["warning"] = warning
        return response
    except (ExpenseManagerError, AIError) as exc:
        return {"success": False, "message": str(exc)}
    except ConfigurationError:
        frappe.logger("expense_manager").exception("api status=config_error create_expense_from_text")
        return {
            "success": False,
            "message": frappe._("AI expense parsing isn't set up yet. Please contact your administrator."),
        }


@frappe.whitelist(methods=["POST"])
def delete_expense(expense):
    user = _current_user()
    try:
        ExpenseService.delete_expense(user, expense)
        return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


def _category_lookup(owner_user: str) -> dict[str, dict]:
	cats = CategoryService.list_categories(owner_user)
	return {c["name"]: {"category_name": c["category_name"], "icon": c.get("icon", "")} for c in cats}


def _enrich_expense(expense: dict, lookup: dict[str, dict]) -> dict:
	cat_id = expense.get("category", "")
	info = lookup.get(cat_id, {})
	expense["category_name"] = info.get("category_name", cat_id)
	expense["category_icon"] = info.get("icon", "")
	return expense


def _enrich_expenses(expenses: list[dict], lookup: dict[str, dict]) -> list[dict]:
	return [_enrich_expense(e, lookup) for e in expenses]


@frappe.whitelist(methods=["GET"])
def list_expenses(dependent=None, category=None, date_from=None, date_to=None, limit=None):
	user = _current_user()
	try:
		data = ExpenseService.list_expenses(
			user,
			dependent=dependent,
			category=category,
			date_from=date_from,
			date_to=date_to,
			limit=cint(limit) if limit else None,
		)
		lookup = _category_lookup(user)
		return _enrich_expenses(data, lookup)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_recent_expenses(dependent=None, limit=10):
	user = _current_user()
	try:
		data = ExpenseService.get_recent_expenses(user, dependent=dependent, limit=cint(limit))
		lookup = _category_lookup(user)
		return _enrich_expenses(data, lookup)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expenses_by_category(category, dependent=None):
	user = _current_user()
	try:
		data = ExpenseService.get_expenses_by_category(user, category, dependent=dependent)
		lookup = _category_lookup(user)
		return _enrich_expenses(data, lookup)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_expenses_by_date_range(date_from, date_to, dependent=None):
	user = _current_user()
	try:
		data = ExpenseService.get_expenses_by_date_range(
			user,
			date_from,
			date_to,
			dependent=dependent,
		)
		lookup = _category_lookup(user)
		return _enrich_expenses(data, lookup)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}