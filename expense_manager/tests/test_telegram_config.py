"""Tests for Telegram and AI configuration access."""

import os
from unittest import TestCase
from unittest.mock import patch

from expense_manager.config.exceptions import ConfigurationError
from expense_manager.telegram import config


class TestTelegramConfig(TestCase):
	"""Verify secure configuration lookup and validation behavior."""

	def setUp(self) -> None:
		"""Clear cached settings before every configuration test."""
		self._clear_configuration_cache()

	def tearDown(self) -> None:
		"""Clear cached settings so tests cannot affect later tests."""
		self._clear_configuration_cache()

	def test_environment_values_override_site_configuration(self) -> None:
		"""Read environment values before values in the active site configuration."""
		with (
			patch.dict(
				os.environ,
				{
					"TELEGRAM_BOT_TOKEN": "environment-token",
					"OPENAI_MODEL": "environment-model",
				},
				clear=True,
			),
			patch.object(
				config.frappe,
				"conf",
				{"telegram_bot_token": "site-token", "openai_model": "site-model"},
			),
		):
			self.assertEqual(config.get_telegram_bot_token(), "environment-token")
			self.assertEqual(config.get_openai_model(), "environment-model")

	def test_site_configuration_and_defaults_are_supported(self) -> None:
		"""Read site configuration and use documented defaults when optional."""
		with patch.dict(os.environ, {}, clear=True), patch.object(
			config.frappe,
			"conf",
			{"telegram_webhook_secret": "site-secret", "use_mock_ai_apis": 1},
		):
			self.assertEqual(config.get_telegram_webhook_secret(), "site-secret")
			self.assertEqual(config.get_openai_model(), "gpt-4o-mini")
			self.assertTrue(config.get_use_mock_ai_apis())

		self._clear_configuration_cache()
		with patch.dict(os.environ, {}, clear=True), patch.object(config.frappe, "conf", {}):
			self.assertFalse(config.get_use_mock_ai_apis())

	def test_all_required_credentials_are_read_from_site_configuration(self) -> None:
		"""Return each required credential when it is present in site configuration."""
		with patch.dict(os.environ, {}, clear=True), patch.object(
			config.frappe,
			"conf",
			{
				"telegram_bot_token": "bot-value",
				"telegram_webhook_secret": "webhook-value",
				"sarvam_api_key": "sarvam-value",
				"openai_api_key": "openai-value",
			},
		):
			self.assertEqual(config.get_telegram_bot_token(), "bot-value")
			self.assertEqual(config.get_telegram_webhook_secret(), "webhook-value")
			self.assertEqual(config.get_sarvam_api_key(), "sarvam-value")
			self.assertEqual(config.get_openai_api_key(), "openai-value")

	def test_missing_required_value_has_a_safe_descriptive_error(self) -> None:
		"""Reject absent credentials without placing a credential in the error."""
		with patch.dict(os.environ, {}, clear=True), patch.object(config.frappe, "conf", {}):
			with self.assertRaisesRegex(ConfigurationError, "telegram_bot_token"):
				config.get_telegram_bot_token()

	def test_mock_mode_rejects_invalid_flag_values(self) -> None:
		"""Reject mock-mode values other than accepted boolean representations."""
		with patch.dict(os.environ, {"USE_MOCK_AI_APIS": "sometimes"}, clear=True), patch.object(
			config.frappe, "conf", {}
		):
			with self.assertRaisesRegex(ConfigurationError, "use_mock_ai_apis"):
				config.get_use_mock_ai_apis()

	@staticmethod
	def _clear_configuration_cache() -> None:
		"""Clear process-local getter caches for isolated configuration tests."""
		for getter in (
			config.get_telegram_bot_token,
			config.get_telegram_webhook_secret,
			config.get_sarvam_api_key,
			config.get_openai_api_key,
			config.get_openai_model,
			config.get_use_mock_ai_apis,
		):
			getter.cache_clear()
