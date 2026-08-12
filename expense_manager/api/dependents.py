"""Whitelisted Dependent endpoints. Thin wrappers only — every rule
lives in DependentService. Scoped to frappe.session.user (the
guardian) — dependents themselves have no desk/REST access, only
Telegram."""

import frappe
from frappe.utils import cint, flt, get_first_day, get_last_day, today

from expense_manager.api.utils import current_user as _current_user
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.report_service import ReportService

# Same rationale as api/budgets.py: DependentService.update_dependent
# distinguishes "field not supplied" from "field explicitly cleared"
# for telegram_username/telegram_user_id via its own private _UNSET.
# This local sentinel preserves that without importing the private one.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_dependent(
	dependent_name: str,
	relationship: str,
	default_monthly_allowance: float,
	telegram_username: str | None = None,
	telegram_user_id: str | None = None,
	allow_carry_forward: int = 1,
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
def get_dependent(dependent: str):
	user = _current_user()
	try:
		return DependentService.get_dependent(user, dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_dependent(
	dependent: str,
	dependent_name: str | None = None,
	relationship: str | None = None,
	default_monthly_allowance: float | None = None,
	telegram_username: str | None = _API_UNSET,
	telegram_user_id: str | None = _API_UNSET,
	allow_carry_forward: int | None = None,
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
def delete_dependent(dependent: str):
	user = _current_user()
	try:
		DependentService.delete_dependent(user, dependent)
		return {"success": True}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_dependent(dependent: str):
	user = _current_user()
	try:
		return DependentService.archive_dependent(user, dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_dependent(dependent: str):
	user = _current_user()
	try:
		return DependentService.restore_dependent(user, dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_dependents(active_only: int = 0):
	user = _current_user()
	try:
		return DependentService.list_dependents(user, active_only=bool(cint(active_only)))
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_dependents(search_text: str | None = None, active_only: int = 1):
	user = _current_user()
	try:
		return DependentService.search_dependents(
			user,
			search_text,
			active_only=bool(cint(active_only)),
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_allowed_categories(dependent: str, active_only: int = 1):
	"""List the categories a dependent may use.

	An empty allowed_categories child table means the dependent may use all
	of the guardian's active categories (the default), which is reflected by
	this endpoint returning the full guardian category list.
	"""
	user = _current_user()
	try:
		return DependentService.list_allowed_categories(
			user,
			dependent,
			active_only=bool(cint(active_only)),
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def add_allowed_category(dependent: str, category: str):
	"""Explicitly allow a guardian-owned category for a dependent.

	``category`` may be a Category doc name or a category name. Idempotent:
	adding an already-allowed category is a no-op.
	"""
	user = _current_user()
	try:
		doc = DependentService.add_allowed_category(user, dependent, category)
		categories = []
		for c in doc.get("allowed_categories") or []:
			cat_val = c.get("category") if hasattr(c, "get") else getattr(c, "category", None)
			if cat_val:
				categories.append(cat_val)
		return {"success": True, "allowed_categories": categories}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def remove_allowed_category(dependent: str, category: str):
	"""Revoke an allowed category from a dependent's list."""
	user = _current_user()
	try:
		doc = DependentService.remove_allowed_category(user, dependent, category)
		categories = []
		for c in doc.get("allowed_categories") or []:
			cat_val = c.get("category") if hasattr(c, "get") else getattr(c, "category", None)
			if cat_val:
				categories.append(cat_val)
		return {"success": True, "allowed_categories": categories}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


# Guest access is required: the dependent portal is opened from a plain
# browser link (no Frappe login). It is secured by validating the opaque
# per-dependent access_token below, which never grants write access.
# nosemgrep: frappe-semgrep-rules.rules.security.guest-whitelisted-method
@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_portal_data(token: str | None = None):
	"""Retrieve full scoped dashboard data for a dependent via access token or ID.

	Returns only this dependent's data:
	- Dependent details
	- Pocket money balance & allocation details (including rollover)
	- Spending breakdown across allowed categories
	- Chronological recent expenses
	- Budget vs actual with overspend flags
	- 6-month spending trend
	"""
	if not token:
		token = frappe.form_dict.get("token")

	if not token:
		return {"success": False, "message": "Access token is required."}

	# Look up by access_token first, then name as fallback
	dep = frappe.db.get_value(
		"Dependent",
		{"access_token": token},
		[
			"name",
			"dependent_name",
			"guardian",
			"relationship",
			"default_monthly_allowance",
			"total_savings",
			"allow_carry_forward",
			"is_active",
			"access_token",
		],
		as_dict=True,
	)
	if not dep:
		dep = frappe.db.get_value(
			"Dependent",
			{"name": token},
			[
				"name",
				"dependent_name",
				"guardian",
				"relationship",
				"default_monthly_allowance",
				"total_savings",
				"allow_carry_forward",
				"is_active",
				"access_token",
			],
			as_dict=True,
		)

	if not dep:
		return {"success": False, "message": "Dependent not found for the provided token."}

	guardian = dep["guardian"]
	dep_id = dep["name"]

	# 1. Pocket Money & Balance
	balance = {}
	try:
		balance = PocketMoneyService.get_balance(guardian, dep_id) or {}
	except Exception:
		balance = {
			"allocation": None,
			"allocated_amount": 0.0,
			"spent_amount": 0.0,
			"carry_forward": 0.0,
			"remaining_amount": 0.0,
			"available_amount": 0.0,
			"total_savings": flt(dep.get("total_savings", 0.0)),
		}

	# 2. Allowed Categories and category spend
	allowed_cats = []
	try:
		allowed_cats = DependentService.list_allowed_categories(guardian, dep_id, active_only=True)
	except Exception:
		allowed_cats = []

	cur_start = balance.get("allocation_date") or get_first_day(today())
	cur_end = balance.get("period_end_date") or get_last_day(today())

	cat_spend_map = {}
	expenses_in_period = frappe.get_all(
		"Expense",
		filters={
			"dependent": dep_id,
			"docstatus": ["!=", 2],
			"expense_date": ["between", [cur_start, cur_end]],
		},
		fields=["category", "amount"],
	)
	for exp in expenses_in_period:
		cat_spend_map[exp.category] = cat_spend_map.get(exp.category, 0.0) + flt(exp.amount)

	category_breakdown = []
	for cat in allowed_cats:
		spent = cat_spend_map.get(cat["name"], 0.0)
		category_breakdown.append(
			{
				"name": cat["name"],
				"category_name": cat["category_name"],
				"icon": cat.get("icon") or "🏷️",
				"spent": round(spent, 2),
			}
		)

	# 3. Budgets vs Actual for this dependent
	budgets = []
	try:
		raw_budgets = BudgetService.list_budgets(guardian, dependent=dep_id, active_only=True)
		for b in raw_budgets:
			usage = BudgetService.get_budget_usage(guardian, b["category"], dependent=dep_id) or {}
			cat_info = CategoryService.get_category(guardian, b["category"])
			budgets.append(
				{
					"name": b["name"],
					"category": b["category"],
					"category_name": cat_info.category_name if cat_info else b["category"],
					"category_icon": (cat_info.icon if cat_info else "🏷️") or "🏷️",
					"allocated_amount": flt(b["allocated_amount"]),
					"spent_amount": flt(usage.get("spent_amount", 0.0)),
					"remaining_amount": flt(usage.get("remaining_amount", b["allocated_amount"])),
					"pct_used": flt(usage.get("pct_used", 0.0)),
					"is_overspent": bool(usage.get("is_overspent", False)),
					"period": b["period"],
					"start_date": str(b["start_date"]),
					"end_date": str(b["end_date"]),
				}
			)
	except Exception:
		budgets = []

	# 4. Recent Expenses
	raw_expenses = frappe.get_all(
		"Expense",
		filters={"dependent": dep_id, "docstatus": ["!=", 2]},
		fields=["name", "amount", "category", "expense_date", "description", "payment_method"],
		order_by="expense_date desc, creation desc",
		limit=30,
	)
	cat_lookup = {c["name"]: c for c in allowed_cats}
	# fallback lookup for any categories not in allowed_cats
	recent_expenses = []
	for e in raw_expenses:
		cat_info = cat_lookup.get(e["category"])
		if not cat_info:
			try:
				c_doc = CategoryService.get_category(guardian, e["category"])
				cat_info = {"category_name": c_doc.category_name, "icon": c_doc.icon}
			except Exception:
				cat_info = {"category_name": e["category"], "icon": "🏷️"}

		recent_expenses.append(
			{
				"name": e["name"],
				"amount": flt(e["amount"]),
				"category": e["category"],
				"category_name": cat_info.get("category_name") or e["category"],
				"category_icon": cat_info.get("icon") or "🏷️",
				"expense_date": str(e["expense_date"]),
				"description": e.get("description") or "",
				"payment_method": e.get("payment_method") or "",
			}
		)

	# 5. 6-Month Spending Trend
	trend = []
	try:
		raw_trend = ReportService.get_spending_trend(guardian, dependent=dep_id, months=6)
		trend = raw_trend or []
	except Exception:
		trend = []

	balance_data = {
		"allocation": balance.get("allocation"),
		"allocated_amount": flt(balance.get("allocated_amount", 0.0)),
		"spent_amount": flt(balance.get("spent_amount", 0.0)),
		"carry_forward": flt(balance.get("carry_forward", 0.0)),
		"remaining_amount": flt(balance.get("remaining_amount", 0.0)),
		"available_amount": flt(balance.get("available_amount", 0.0)),
		"total_savings": flt(balance.get("total_savings", dep.get("total_savings", 0.0))),
		"allocation_period": balance.get("allocation_period") or "Monthly",
		"allocation_date": str(balance.get("allocation_date")) if balance.get("allocation_date") else None,
		"period_end_date": str(balance.get("period_end_date")) if balance.get("period_end_date") else None,
	}

	return {
		"success": True,
		"dependent": {
			"name": dep["name"],
			"dependent_name": dep["dependent_name"],
			"relationship": dep["relationship"],
			"default_monthly_allowance": flt(dep["default_monthly_allowance"]),
			"total_savings": flt(dep.get("total_savings", 0.0)),
			"allow_carry_forward": bool(dep.get("allow_carry_forward", 1)),
			"access_token": dep["access_token"],
		},
		"balance": balance_data,
		"pocket_money": balance_data,
		"category_breakdown": category_breakdown,
		"allowed_categories": category_breakdown,
		"budgets": budgets,
		"recent_expenses": recent_expenses,
		"trend": trend,
	}
