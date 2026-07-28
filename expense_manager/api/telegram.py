"""Whitelisted Telegram linking endpoints, reachable from the desk UI.
No Telegram-specific formatting here — just plain dicts."""

import frappe

from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.api.utils import current_user as _current_user


@frappe.whitelist(methods=["POST"])
def generate_link_code():
	user = _current_user()

	try:
		return TelegramLinkService.link_account(user)
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_link_status():
	user = _current_user()

	try:
		return {"linked": TelegramLinkService.is_linked(user)}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def unlink():
	user = _current_user()

	try:
		TelegramLinkService.unlink_account(user)
		return {"success": True}
    except ExpenseManagerError as exc:
        return {"success": False, "message": str(exc)}