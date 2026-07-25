"""Reply text for the Telegram /profile and /settings commands."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_profile(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	result = TelegramService.get_link_status(telegram_user_id)
	if not result["success"] or not result["data"]["linked"]:
		return "Your Telegram account isn't linked yet. Send /link to get started."

	data = result["data"]
	role = "Dependent" if data["is_dependent"] else "Individual"
	return f"Role: {role}\nAccount: {data['owner_user']}"


def handle_settings(update: dict[str, object]) -> str:
	return "Settings management isn't available yet. Check back soon!"
