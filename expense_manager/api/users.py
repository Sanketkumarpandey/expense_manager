"""Whitelisted User-provisioning endpoints. Thin wrappers only — every rule
lives in the service layer. Admin-only guardian onboarding: there is no
self-service signup, and guardian accounts are provisioned here or via the
Desk New User form (the latter does not auto-grant the role). Dependents
never get a Frappe User, so they are explicitly out of scope for this
endpoint."""

import frappe
from frappe import _
from frappe.utils import validate_email_address

from expense_manager.constants.roles import GUARDIAN_ROLE
from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import ExpenseManagerError


@frappe.whitelist(methods=["POST"])
def register_guardian(
	email: str, first_name: str, last_name: str | None = None, send_welcome_email: bool = True
):
	"""Provision a guardian User with the Expense Manager User role and seed
	their default categories.

	Admin-only: rejects Guest, Expense Manager Users, and any non-privileged
	caller — including one attempting to self-elevate. Idempotent for
	existing Users (role/categories are ensured, never duplicated). The
	response never includes a password or any User field beyond email.
	"""
	_require_admin()

	email = str(email or "").strip().lower()
	if not email:
		frappe.throw(_("email is required."), frappe.ValidationError)
	validate_email_address(email, throw=True)

	first_name = str(first_name or "").strip()
	if not first_name:
		frappe.throw(_("first_name is required."), frappe.ValidationError)

	try:
		if frappe.db.exists("User", email):
			user = frappe.get_doc("User", email)
			if GUARDIAN_ROLE not in frappe.get_roles(email):
				user.add_roles(GUARDIAN_ROLE)
			CategoryService.create_default_categories(email)
			return {"success": True, "user": email, "created": False}

		frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name,
				"send_welcome_email": send_welcome_email,
				"roles": [{"role": GUARDIAN_ROLE}],
			}
		).insert(ignore_permissions=True)
		CategoryService.create_default_categories(email)
		return {"success": True, "user": email, "created": True}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


def _require_admin() -> None:
	"""Reject any session that isn't Administrator or System Manager.

	Must run first, before any input validation, so a non-privileged caller
	can never influence provisioning (including self-elevation attempts).
	"""
	session_user = frappe.session.user
	if session_user == "Administrator":
		return
	if "System Manager" in frappe.get_roles(session_user):
		return
	raise frappe.PermissionError(_("Only an Administrator or System Manager can register guardian users."))
