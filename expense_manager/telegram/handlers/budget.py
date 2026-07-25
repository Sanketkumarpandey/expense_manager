"""Reply text for the Telegram /budgets and /balance commands."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_budgets(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_budget(telegram_user_id)
	if not result["success"]:
		return result["message"]

	budgets = result["data"]
	if not budgets:
		return "You don't have any budgets set up yet."

	lines = ["Your budgets:"]
	for budget in budgets:
		lines.append(
			f"- {budget['category_name']}: {budget['spent_amount']} / {budget['allocated_amount']} "
			f"({budget['percentage']}%{' — over budget' if budget['is_overspent'] else ''})"
		)
	return "\n".join(lines)

def handle_balance(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	status = TelegramService.get_link_status(telegram_user_id)
	if not status["success"] or not status["data"]["linked"]:
		return "Your Telegram account isn't linked yet. Send /link to get started."

	if status["data"]["is_dependent"]:
		result = TelegramService.get_pocket_money(telegram_user_id)
		if not result["success"]:
			return result["message"]

		balances = result["data"]
		if not balances:
			return "You don't have a pocket money allocation set up yet."

		balance = balances[0]
		return f"Your pocket money balance: {balance.get('remaining_amount', balance)}"

	result = TelegramService.get_budget(telegram_user_id)
	if not result["success"]:
		return result["message"]

	budgets = result["data"]
	if not budgets:
		return "You don't have any budgets set up yet."

	lines = ["Your budget balances:"]
	for budget in budgets:
		lines.append(f"- {budget.get('category')}: remaining {budget.get('remaining_amount', '')}")
	return "\n".join(lines)
