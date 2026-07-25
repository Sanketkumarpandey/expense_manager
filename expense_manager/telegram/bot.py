"""Background Telegram command dispatcher and safe reply boundary."""

import frappe

from expense_manager.telegram.router import route_update
from expense_manager.telegram.services.telegram_service import send_message


def process_update(update: dict[str, object]) -> None:
	"""Route one queued update and send its text reply without domain processing."""
	try:
		response_text = route_update(update)
		if response_text is None:
			return
		chat_id = _get_chat_id(update)
		if chat_id is None:
			frappe.logger("expense_manager").warning(
				"telegram_bot status=ignored_missing_chat_id"
			)
			return
		send_message(chat_id, response_text)
		frappe.logger("expense_manager").info("telegram_bot status=reply_completed")
	except Exception:
		frappe.logger("expense_manager").exception("telegram_bot status=error")


def _get_chat_id(update: dict[str, object]) -> str | int | None:
	"""Extract a valid chat identifier from a message without resolving identity."""
	message = update.get("message") if isinstance(update, dict) else None
	chat = message.get("chat") if isinstance(message, dict) else None
	chat_id = chat.get("id") if isinstance(chat, dict) else None
	if isinstance(chat_id, (str, int)) and not isinstance(chat_id, bool):
		return chat_id
	return None
