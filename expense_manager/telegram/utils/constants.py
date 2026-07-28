"""Telegram integration constants: timeouts, retry config, and shared values."""

_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
_TELEGRAM_FILE_BASE_URL = "https://api.telegram.org/file"

# Timeouts in seconds
SEND_MESSAGE_TIMEOUT = 10
SEND_PHOTO_TIMEOUT = 15
GET_FILE_TIMEOUT = 10
DOWNLOAD_FILE_TIMEOUT = 30

# Retry config for Telegram API calls
TELEGRAM_MAX_RETRIES = 2
TELEGRAM_RETRY_BACKOFF_BASE = 1.0
