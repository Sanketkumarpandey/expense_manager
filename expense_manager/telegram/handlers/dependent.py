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

	status = TelegramService.get_link_status(telegram_user_id)
	if not status["success"] or not status["data"]["linked"]:
		return "Your Telegram account isn't linked yet. Send /link to get started."

	result = TelegramService.get_pocket_money(telegram_user_id)
	if not result["success"]:
		return result["message"]

	allocations = result["data"]
	if not allocations:
		return "No pocket money allocations found."

	if status["data"]["is_dependent"]:
		allocation = allocations[0]
		return (
			f"Pocket money: {allocation.get('total_available_amount')} available "
			f"(of {allocation.get('allocated_amount')} allocated)."
		)

	dependents_result = TelegramService.list_dependents(telegram_user_id)
	name_lookup = {}
	if dependents_result["success"]:
		name_lookup = {row["name"]: row["dependent_name"] for row in dependents_result["data"]}

	lines = ["Pocket money:"]
	for allocation in allocations:
		dependent_id = allocation.get("dependent")
		display_name = name_lookup.get(dependent_id, dependent_id)
		lines.append(
			f"- {display_name}: {allocation.get('total_available_amount')} available "
			f"(of {allocation.get('allocated_amount')} allocated)"
		)
	return "\n".join(lines)


def handle_savings(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_pocket_money(telegram_user_id)
	if not result["success"]:
		return result["message"]

	balances = result["data"]
	if not balances:
		return "You don't have a pocket money allocation set up yet."

	balance = balances[0]
	return f"Your savings (carried forward): {balance.get('carry_forward', 0)}"


def handle_rollover(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.rollover_pocket_money(telegram_user_id)
	return result["message"]