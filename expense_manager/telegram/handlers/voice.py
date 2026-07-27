"""Reply text for Telegram voice note messages."""

import os

from expense_manager.telegram.services.telegram_service import TelegramService
from expense_manager.telegram.utils.helpers import get_telegram_user_id
from expense_manager.telegram.utils.file_download import download_voice_file


def handle_voice(update: dict[str, object]) -> str:
	telegram_user_id = get_telegram_user_id(update)
	if telegram_user_id is None:
		return "I couldn't identify your Telegram account. Please try again."

	message = update.get("message") if isinstance(update, dict) else None
	voice = message.get("voice") if isinstance(message, dict) else None
	file_id = voice.get("file_id") if isinstance(voice, dict) else None

	if not file_id:
		return "I couldn't find a voice note in that message."

	file_path = None
	try:
		file_path = download_voice_file(file_id)
		result = TelegramService.create_expense_from_voice(telegram_user_id, file_path)
	except Exception:
		return "Sorry, I couldn't process that voice note. Please try again or type your expense instead."
	finally:
		if file_path and os.path.exists(file_path):
			os.remove(file_path)

	return result["message"]