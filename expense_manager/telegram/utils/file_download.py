"""Download a Telegram voice file to a local temp path for transcription."""

import os
import tempfile

import requests

from expense_manager.services.exceptions import TelegramError
from expense_manager.telegram.config import get_telegram_bot_token
from expense_manager.telegram.utils.constants import (
	_TELEGRAM_API_BASE_URL,
	_TELEGRAM_FILE_BASE_URL,
	DOWNLOAD_FILE_TIMEOUT,
	GET_FILE_TIMEOUT,
)


def download_voice_file(file_id: str) -> str:
	token = get_telegram_bot_token()

	get_file_response = requests.get(
		f"{_TELEGRAM_API_BASE_URL}/bot{token}/getFile",
		params={"file_id": file_id},
		timeout=GET_FILE_TIMEOUT,
	)
	get_file_response.raise_for_status()

	body = get_file_response.json()
	if not isinstance(body, dict) or not body.get("ok"):
		raise TelegramError(f"Telegram getFile returned an error: {body.get('description', body)}")

	result = body.get("result")
	if not isinstance(result, dict):
		raise TelegramError("Telegram getFile response missing result.")

	remote_path = result.get("file_path")
	if not remote_path:
		raise TelegramError("Telegram getFile result missing file_path.")

	download_response = requests.get(
		f"{_TELEGRAM_FILE_BASE_URL}/bot{token}/{remote_path}",
		timeout=DOWNLOAD_FILE_TIMEOUT,
	)
	download_response.raise_for_status()

	suffix = os.path.splitext(remote_path)[1] or ".ogg"
	with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
		tmp.write(download_response.content)
		return tmp.name
