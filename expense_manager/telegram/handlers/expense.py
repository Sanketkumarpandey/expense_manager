"""Reply text for the Telegram /expenses, /categories, /addexpense commands,
and free-text fallback (voice handled in voice.py)."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_expenses(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	return TelegramService.build_expenses_display(telegram_user_id)


def handle_categories(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.list_categories(telegram_user_id)
	if not result["success"]:
		return result["message"]

	categories = result["data"]
	if not categories:
		return "You don't have any categories set up yet."

	lines = ["Your categories:"]
	for category in categories:
		icon = category.get("icon", "") or ""
		name = category.get("category_name", "")
		prefix = f"{icon} " if icon else ""
		lines.append(f"- {prefix}{name}")
	return "\n".join(lines)


def handle_addexpense(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	message = update.get("message") if isinstance(update, dict) else None
	full_text = message.get("text", "") if isinstance(message, dict) else ""
	parts = full_text.strip().split(maxsplit=1)
	description = parts[1] if len(parts) > 1 else ""

	if not description:
		return "Please describe your expense. Example: /addexpense lunch 250"

	result = TelegramService.create_expense_from_text(telegram_user_id, description)
	if not result["success"]:
		return result["message"]
	return result["message"]


def handle_free_text(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	message = update.get("message") if isinstance(update, dict) else None
	text = message.get("text", "") if isinstance(message, dict) else ""

	result = TelegramService.create_expense_from_text(telegram_user_id, text)
	if not result["success"]:
		return result["message"]
	return result["message"]
