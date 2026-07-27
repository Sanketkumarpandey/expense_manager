"""Download a Telegram voice file to a local temp path for transcription."""

import os
import tempfile

import requests

from expense_manager.telegram.config import get_telegram_bot_token


_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
_TELEGRAM_FILE_BASE_URL = "https://api.telegram.org/file"


def download_voice_file(file_id: str) -> str:
	token = get_telegram_bot_token()

	get_file_response = requests.get(
		f"{_TELEGRAM_API_BASE_URL}/bot{token}/getFile",
		params={"file_id": file_id},
		timeout=10,
	)
	get_file_response.raise_for_status()
	remote_path = get_file_response.json()["result"]["file_path"]

	download_response = requests.get(
		f"{_TELEGRAM_FILE_BASE_URL}/bot{token}/{remote_path}",
		timeout=30,
	)
	download_response.raise_for_status()

	suffix = os.path.splitext(remote_path)[1] or ".ogg"
	with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
		tmp.write(download_response.content)
		return tmp.name