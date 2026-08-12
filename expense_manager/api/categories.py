"""Whitelisted Category endpoints. Thin wrappers only — every rule
lives in CategoryService. All scoped to frappe.session.user, since
Categories belong to the guardian (desk user) and are a shared,
guardian-owned pool; dependents have no desk/REST access. A dependent's
effective categories are managed via the dependent's allowed_categories
child table — see api/dependents.py."""

import frappe
from frappe.utils import cint

from expense_manager.api.utils import current_user as _current_user
from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import ExpenseManagerError


@frappe.whitelist(methods=["POST"])
def create_category(category_name: str, icon: str | None = None):
	user = _current_user()
	try:
		return CategoryService.create_category(user, category_name, icon).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_category(category: str):
	user = _current_user()
	try:
		return CategoryService.get_category(user, category).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_category(
	category: str, category_name: str | None = None, icon: str | None = None, is_active: int | None = None
):
	user = _current_user()
	try:
		return CategoryService.update_category(
			user,
			category,
			category_name=category_name,
			icon=icon,
			is_active=None if is_active is None else bool(cint(is_active)),
		).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_category(category: str):
	user = _current_user()
	try:
		CategoryService.delete_category(user, category)
		return {"success": True}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_category(category: str):
	user = _current_user()
	try:
		return CategoryService.archive_category(user, category).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_category(category: str):
	user = _current_user()
	try:
		return CategoryService.restore_category(user, category).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_categories(active_only: int = 0):
	user = _current_user()
	try:
		return CategoryService.list_categories(user, active_only=bool(cint(active_only)))
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_categories(search_text: str | None = None, active_only: int = 1):
	user = _current_user()
	try:
		return CategoryService.search_categories(
			user,
			search_text,
			active_only=bool(cint(active_only)),
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def create_default_categories():
	user = _current_user()
	try:
		return [doc.as_dict() for doc in CategoryService.create_default_categories(user)]
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}
