"""Scripted row-level permissions for Expense.

The Expense Manager User role can create/read/write Expense records,
but only for rows owned by the current session user. These hooks
scope list queries and every document-level permission check to
``owner_user``, so one guardian can never read or mutate another
guardian's expenses.

System Manager and Administrator stay unrestricted.

Hooks are wired in ``hooks.py`` under ``permission_query_conditions``
and ``has_permission``.
"""

import frappe


def _is_privileged(user: str | None) -> bool:
	"""True for the users that manage the whole instance."""
	if not user:
		user = frappe.session.user
	if user == "Administrator":
		return True
	roles = frappe.get_roles(user)
	return "System Manager" in roles


def expense_permission_query_conditions(user=None, **kwargs):
	"""Restrict every Expense list/select to rows owned by ``user``."""
	if _is_privileged(user):
		return None
	user = user or frappe.session.user
	return f"`tabExpense`.`owner_user` = {frappe.db.escape(user)}"


def expense_has_permission(doc, ptype="read", user=None, **kwargs):
	"""Deny access to Expense documents the user does not own.

	Controllers can only deny what the role permission table already
	granted — they never expand access. ``create`` runs before
	``before_insert``, so the client-supplied ``owner_user`` is visible
	here: a create that names another owner is rejected outright.
	"""
	if _is_privileged(user):
		return True

	user = user or frappe.session.user

	if ptype == "create":
		if not getattr(doc, "owner_user", None):
			return True
		return doc.owner_user == user

	return getattr(doc, "owner_user", None) == user
