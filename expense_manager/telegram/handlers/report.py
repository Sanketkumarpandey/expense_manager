"""Reply text for the Telegram /report command."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_report(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_monthly_report(telegram_user_id)
	if not result["success"]:
		return result["message"]

	months = result["data"]
	lines = ["Your monthly report:"]
	for row in months:
		if row["total_amount"]:
			lines.append(f"- {row['month']}: {row['total_amount']}")
	return "\n".join(lines) if len(lines) > 1 else "No expenses recorded this year."