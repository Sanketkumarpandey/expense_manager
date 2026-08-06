"""Command and voice routing for validated Telegram message updates."""

from collections.abc import Callable, Mapping

import frappe

from expense_manager.telegram.handlers.account import handle_profile, handle_settings
from expense_manager.telegram.handlers.budget import handle_balance, handle_budgets
from expense_manager.telegram.handlers.dependent import (
	handle_dependents,
	handle_pocketmoney,
	handle_rollover,
	handle_savings,
)
from expense_manager.telegram.handlers.expense import (
	handle_categories,
	handle_expenses,
	handle_addexpense,
	handle_free_text,
)
from expense_manager.telegram.handlers.help import handle_help
from expense_manager.telegram.handlers.link import handle_link
from expense_manager.telegram.handlers.report import handle_report
from expense_manager.telegram.handlers.start import handle_start
from expense_manager.telegram.handlers.unknown import handle_unknown
from expense_manager.telegram.handlers.unlink import handle_unlink
from expense_manager.telegram.handlers.voice import handle_voice
from expense_manager.services.exceptions import ExpenseManagerError


Handler = Callable[[dict[str, object]], str]

COMMAND_DESCRIPTIONS: Mapping[str, list[tuple[str, str]]] = {
	"Account": [
		("start", "welcome message"),
		("help", "show this help"),
		("link", "<code> — link your account"),
		("unlink", "unlink your account"),
		("profile", "view your profile"),
		("settings", "account settings"),
	],
	"Expenses & Budgets": [
		("addexpense", "<text> — log an expense by text"),
		("expenses", "view recent expenses"),
		("categories", "view your categories"),
		("budgets", "view your budgets"),
		("balance", "check your balance"),
		("report", "spending report chart"),
	],
	"Dependents": [
		("dependents", "manage dependents"),
		("pocketmoney", "pocket money allocations"),
		("savings", "view your savings"),
		("rollover", "roll over pocket money"),
	],
}


COMMAND_HANDLERS: Mapping[str, Handler] = {
	"start": handle_start,
	"help": handle_help,
	"link": handle_link,
	"unlink": handle_unlink,
	"profile": handle_profile,
	"settings": handle_settings,
	"expenses": handle_expenses,
	"addexpense": handle_addexpense,
	"categories": handle_categories,
	"budgets": handle_budgets,
	"balance": handle_balance,
	"report": handle_report,
	"dependents": handle_dependents,
	"pocketmoney": handle_pocketmoney,
	"savings": handle_savings,
	"rollover": handle_rollover,
}


def route_update(update: dict[str, object]) -> str | None:
	"""Dispatch a Telegram voice note or text command to its handler."""
	try:
		message = _get_message(update)
		if message is None:
			frappe.logger("expense_manager").info(
				"telegram_router status=ignored_unsupported_update"
			)
			return None

		# Voice messages are not commands, so dispatch them before text routing.
		if isinstance(message.get("voice"), dict):
			frappe.logger("expense_manager").info(
				"telegram_router status=selected handler=handle_voice"
			)
			response = handle_voice(update)
			frappe.logger("expense_manager").info(
				"telegram_router status=completed handler=handle_voice"
			)
			return response

		text = message.get("text")
		if not isinstance(text, str) or not text.strip():
			frappe.logger("expense_manager").info(
				"telegram_router status=ignored_missing_text"
			)
			return None

		command = _extract_command(text)
		if not command:
			handler = handle_free_text
		else:
			handler = COMMAND_HANDLERS.get(command, handle_unknown)
		handler_name = getattr(handler, "__name__", "unknown_handler")

		frappe.logger("expense_manager").info(
			"telegram_router command=%s handler=%s status=selected",
			command,
			handler_name,
		)

		response = handler(update)

		frappe.logger("expense_manager").info(
			"telegram_router command=%s handler=%s status=completed",
			command,
			handler_name,
		)

		return response

	except ExpenseManagerError as exc:
		frappe.logger("expense_manager").info(
			"telegram_router status=domain_error message=%s",
			str(exc),
		)
		return str(exc)

	except Exception:
		frappe.logger("expense_manager").exception(
			"telegram_router status=error"
		)
		return "Sorry, something went wrong. Please try again later."


def _get_message(update: dict[str, object]) -> dict[str, object] | None:
	"""Return the Telegram message object when this update has one."""
	if not isinstance(update, dict):
		return None

	message = update.get("message")
	return message if isinstance(message, dict) else None


def _extract_command(text: str) -> str:
	"""Normalize a Telegram command, including an optional bot username suffix."""
	first_word = text.strip().split(maxsplit=1)[0]

	if not first_word.startswith("/"):
		return ""

	command = first_word[1:].split("@", maxsplit=1)[0]
	return command.lower()