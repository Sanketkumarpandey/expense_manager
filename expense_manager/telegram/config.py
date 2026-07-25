"""Secure configuration access for Telegram and AI integrations.

This module reads configuration from process environment variables first and
the active Frappe site's configuration second. It never logs configuration
values, particularly credentials.
"""

import os
from functools import lru_cache

import frappe

from expense_manager.config.exceptions import ConfigurationError


_DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES = frozenset({"0", "false", "no", "off", ""})


def _get_config_value(environment_key: str, site_config_key: str) -> object:
	"""Return an environment value first, then the active site's config value."""
	return os.environ.get(environment_key, frappe.conf.get(site_config_key))


def _get_required_string(environment_key: str, site_config_key: str) -> str:
	"""Return a non-empty credential without including its value in an error."""
	value = _get_config_value(environment_key, site_config_key)
	if not isinstance(value, str) or not value.strip():
		raise ConfigurationError(
			f"Missing required configuration '{site_config_key}'. "
			f"Set {environment_key} or {site_config_key} in site_config.json."
		)
	return value.strip()


@lru_cache(maxsize=1)
def get_telegram_bot_token() -> str:
	"""Return the required Telegram bot token; never log or expose it."""
	return _get_required_string("TELEGRAM_BOT_TOKEN", "telegram_bot_token")


@lru_cache(maxsize=1)
def get_telegram_webhook_secret() -> str:
	"""Return the required Telegram webhook secret; never log or expose it."""
	return _get_required_string("TELEGRAM_WEBHOOK_SECRET", "telegram_webhook_secret")


@lru_cache(maxsize=1)
def get_sarvam_api_key() -> str:
	"""Return the required Sarvam API key; never log or expose it."""
	return _get_required_string("SARVAM_API_KEY", "sarvam_api_key")


@lru_cache(maxsize=1)
def get_openai_api_key() -> str:
	"""Return the required OpenAI API key; never log or expose it."""
	return _get_required_string("OPENAI_API_KEY", "openai_api_key")


@lru_cache(maxsize=1)
def get_openai_model() -> str:
	"""Return the configured OpenAI model or the documented default model."""
	value = _get_config_value("OPENAI_MODEL", "openai_model")
	if value is None:
		return _DEFAULT_OPENAI_MODEL
	if not isinstance(value, str) or not value.strip():
		raise ConfigurationError(
			"Invalid configuration 'openai_model'. Set OPENAI_MODEL or "
			"openai_model in site_config.json to a non-empty model name."
		)
	return value.strip()


@lru_cache(maxsize=1)
def get_use_mock_ai_apis() -> bool:
	"""Return whether AI adapters must use deterministic mock implementations."""
	value = _get_config_value("USE_MOCK_AI_APIS", "use_mock_ai_apis")
	if value is None:
		return False
	if isinstance(value, bool):
		return value
	if isinstance(value, int) and value in (0, 1):
		return bool(value)
	if isinstance(value, str):
		normalized_value = value.strip().lower()
		if normalized_value in _TRUE_VALUES:
			return True
		if normalized_value in _FALSE_VALUES:
			return False
	raise ConfigurationError(
		"Invalid configuration 'use_mock_ai_apis'. Set USE_MOCK_AI_APIS or "
		"use_mock_ai_apis to 0 or 1."
	)
