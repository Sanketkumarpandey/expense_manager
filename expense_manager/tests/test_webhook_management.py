"""Tests for Telegram webhook management utilities with mocked HTTP requests."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from expense_manager.telegram import webhook_management


class TestWebhookManagement(TestCase):
	"""Verify registration utilities never require a live Telegram API call in tests."""

	def setUp(self) -> None:
		"""Patch all configuration, logging, and HTTP dependencies for each test."""
		self.response = MagicMock()
		self.response.json.return_value = {"ok": True, "result": True}
		self.patches = (
			patch("expense_manager.telegram.webhook_management.requests.post", return_value=self.response),
			patch(
				"expense_manager.telegram.webhook_management.get_telegram_bot_token", return_value="bot-token"
			),
			patch(
				"expense_manager.telegram.webhook_management.get_telegram_webhook_secret",
				return_value="webhook-secret",
			),
			patch.object(webhook_management.frappe, "logger"),
		)
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self) -> None:
		"""Stop all mocks after each management-utility test."""
		for active_patch in reversed(self.patches):
			active_patch.stop()

	def test_register_webhook_uses_configured_secret(self) -> None:
		"""Register a supplied endpoint with a mocked Telegram API request."""
		endpoint_url = "https://example.test/telegram"

		self.assertEqual(webhook_management.register_webhook(endpoint_url), {"ok": True, "result": True})
		webhook_management.requests.post.assert_called_once_with(
			"https://api.telegram.org/botbot-token/setWebhook",
			data={"url": endpoint_url, "secret_token": "webhook-secret"},
			timeout=10,
		)

	def test_deregister_webhook_and_inspect_info_use_mocked_requests(self) -> None:
		"""Call deregistration and inspection methods without live Telegram traffic."""
		self.assertTrue(webhook_management.deregister_webhook()["ok"])
		self.assertTrue(webhook_management.get_webhook_info()["ok"])
		self.assertEqual(webhook_management.requests.post.call_count, 2)
