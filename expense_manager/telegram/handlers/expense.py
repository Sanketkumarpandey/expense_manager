"""Reply text for the Telegram /expenses and /categories commands (voice handled in voice.py)."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_expenses(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.list_expenses(telegram_user_id)
	if not result["success"]:
		return result["message"]

	expenses = result["data"]
	if not expenses:
		return "You don't have any recent expenses."

	lines = ["Your recent expenses:"]
	for expense in expenses:
		lines.append(
			f"- {expense.get('expense_date')} | {expense.get('category_name', expense.get('category'))} | {expense.get('amount')}"
		)
	return "\n".join(lines)


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
		lines.append(f"- {category.get('category_name')}")
	return "\n".join(lines)
