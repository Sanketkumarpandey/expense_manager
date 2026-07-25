"""Reply text for the Telegram /dependents, /pocketmoney, /savings, /rollover commands."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_dependents(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.list_dependents(telegram_user_id)
	if not result["success"]:
		return result["message"]

	dependents = result["data"]
	if not dependents:
		return "You don't have any dependents added yet."

	lines = ["Your dependents:"]
	for dependent in dependents:
		lines.append(f"- {dependent.get('dependent_name')} ({dependent.get('relationship')})")
	return "\n".join(lines)


def handle_pocketmoney(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_pocket_money(telegram_user_id)
	if not result["success"]:
		return result["message"]

	allocations = result["data"]
	if not allocations:
		return "No pocket money allocations found."

	lines = ["Pocket money:"]
	for allocation in allocations:
		lines.append(f"- {allocation}")
	return "\n".join(lines)


def handle_savings(update: dict[str, object]) -> str:
	return "Savings tracking isn't available yet. Check back soon!"


def handle_rollover(update: dict[str, object]) -> str:
	return "Pocket money rollover isn't available yet. Check back soon!"
