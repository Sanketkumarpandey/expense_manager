"""Whitelisted Category endpoints. Thin wrappers only — every rule
lives in CategoryService. All scoped to frappe.session.user, since
Categories belong to the guardian (desk user); dependents have no
desk/REST access."""

import frappe
from frappe.utils import cint

from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.api.utils import current_user as _current_user


@frappe.whitelist(methods=["POST"])
def create_category(category_name, icon=None):
    user = _current_user()
    try:
        return CategoryService.create_category(user, category_name, icon).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_category(category):
    user = _current_user()
    try:
        return CategoryService.get_category(user, category).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_category(category, category_name=None, icon=None, is_active=None):
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
def delete_category(category):
    user = _current_user()
    try:
        CategoryService.delete_category(user, category)
        return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_category(category):
    user = _current_user()
    try:
        return CategoryService.archive_category(user, category).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_category(category):
    user = _current_user()
    try:
        return CategoryService.restore_category(user, category).as_dict()
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_categories(active_only=0):
    user = _current_user()
    try:
        return CategoryService.list_categories(user, active_only=bool(cint(active_only)))
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_categories(search_text=None, active_only=1):
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