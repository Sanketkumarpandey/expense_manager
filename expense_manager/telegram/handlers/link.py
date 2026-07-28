"""Reply text for the Telegram /link command."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_link(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	status = TelegramService.get_link_status(telegram_user_id)
	if status["success"] and status["data"]["linked"]:
		return "Your account is already linked. Send /unlink first if you want to relink."

	message = update.get("message") if isinstance(update, dict) else {}
	text = message.get("text", "") if isinstance(message, dict) else ""
	parts = text.strip().split(maxsplit=1)

	if len(parts) < 2:
		return (
			"To link your account, generate a linking code from the Expense Manager "
			"desk (your profile → 'Link Telegram'), then send:\n"
			"/link <code>"
		)

	token = parts[1].strip()
	from_user = message.get("from", {}) if isinstance(message, dict) else {}

	result = TelegramService.complete_link(
		telegram_user_id,
		token,
		telegram_username=from_user.get("username"),
		first_name=from_user.get("first_name"),
		last_name=from_user.get("last_name"),
		language_code=from_user.get("language_code"),
	)
	return result["message"]