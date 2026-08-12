"""Reply text for the Telegram /unlink command."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_unlink(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	message = update.get("message") if isinstance(update, dict) else {}
	text = message.get("text", "") if isinstance(message, dict) else ""
	parts = text.strip().split(maxsplit=1)

	if len(parts) < 2 or parts[1].strip().lower() != "confirm":
		return "This will unlink your Telegram account. Send {/unlink confirm } to proceed."

	result = TelegramService.unlink_account(telegram_user_id)
	return result["message"]
