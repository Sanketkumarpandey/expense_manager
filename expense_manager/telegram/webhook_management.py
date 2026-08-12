"""Administrative Telegram webhook registration utilities without update handling."""

from typing import cast

import frappe
import requests

from expense_manager.telegram.config import get_telegram_bot_token, get_telegram_webhook_secret

_WEBHOOK_METHOD_PATH = "/api/method/expense_manager.telegram.webhook.handle"
_TELEGRAM_API_BASE_URL = "https://api.telegram.org"


def register_webhook(webhook_url: str | None = None) -> dict[str, object]:
	"""Register the configured Telegram webhook; it does not process any updates."""
	endpoint_url = webhook_url or _get_webhook_endpoint_url()
	result = _call_telegram_api(
		"setWebhook",
		{"url": endpoint_url, "secret_token": get_telegram_webhook_secret()},
	)
	_log_management_event("registered")
	return result


def deregister_webhook() -> dict[str, object]:
	"""Remove the configured Telegram webhook; it does not alter application data."""
	result = _call_telegram_api("deleteWebhook", {"drop_pending_updates": False})
	_log_management_event("deregistered")
	return result


def get_webhook_info() -> dict[str, object]:
	"""Retrieve Telegram webhook metadata for testing; it does not send an update."""
	result = _call_telegram_api("getWebhookInfo", {})
	_log_management_event("inspected")
	return result


def _get_webhook_endpoint_url() -> str:
	"""Build the public webhook URL from the active Frappe site URL."""
	return f"{frappe.utils.get_url().rstrip('/')}{_WEBHOOK_METHOD_PATH}"


def _call_telegram_api(method: str, payload: dict[str, object]) -> dict[str, object]:
	"""Call one Telegram management endpoint without logging credentials or payloads."""
	bot_token = get_telegram_bot_token()
	response = requests.post(f"{_TELEGRAM_API_BASE_URL}/bot{bot_token}/{method}", data=payload, timeout=10)
	response.raise_for_status()
	response_payload = response.json()
	if not isinstance(response_payload, dict):
		raise ValueError("Telegram returned an invalid webhook management response.")
	return cast(dict[str, object], response_payload)


def _log_management_event(status: str) -> None:
	"""Log a management operation outcome without exposing Telegram credentials."""
	frappe.logger("expense_manager").info("telegram_webhook_management status=%s", status)
