"""Shared helpers for the REST API layer."""

import frappe
from frappe import _

from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import ExpenseManagerError


def current_user() -> str:
	"""Return the authenticated Frappe session user or abort with 401."""
	user = frappe.session.user
	if user == "Guest":
		frappe.throw("You must be logged in.")
	return user


def resolve_category_id(
	owner_user: str,
	category: str,
) -> str:
	"""Resolve a category supplied by a client to the actual Category doc name.

	Category docs use a random hash autoname, so clients may pass either the
	doc name itself or the human-readable category_name. If ``category`` is an
	existing Category doc name it is returned directly (ownership still
	validated); otherwise it is matched case-insensitively against the user's
	shared (guardian-owned) category names. Categories are no longer scoped
	per dependent, so no dependent argument exists here.
	"""
	if frappe.db.exists("Category", category):
		cat = CategoryService.get_category(owner_user, category)
		return cat.name

	categories = CategoryService.list_categories(owner_user)
	for cat in categories:
		if cat["category_name"].lower() == category.strip().lower():
			return cat["name"]

	raise ExpenseManagerError(
		_("Category '{0}' not found. Please use an existing category name.").format(category)
	)
