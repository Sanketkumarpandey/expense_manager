"""Reply text for the Telegram /start command."""

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id


def handle_start(update: dict[str, object]) -> str:
	"""Return a welcome message, personalised when the user is already linked."""
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "Hi! I'm your Expense Manager bot. Send /help to see the available commands."

	try:
		status = TelegramService.get_link_status(telegram_user_id)
	except Exception:
		return "Hi! I'm your Expense Manager bot. Send /help to see the available commands."

	if not status.get("success") or not status.get("data", {}).get("linked"):
		return "Hi! I'm your Expense Manager bot. Send /help to see the available commands."

	data = status["data"]
	role = "Dependent" if data.get("is_dependent") else "Individual"
	return f"Welcome back! You are linked as a {role}.\nSend /help to see the available commands."
