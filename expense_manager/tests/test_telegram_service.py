"""Unit tests for the minimal Telegram sendMessage transport."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from expense_manager.telegram.services import telegram_service
from expense_manager.telegram.utils.constants import SEND_MESSAGE_TIMEOUT


class TestTelegramService(TestCase):
	"""Verify sendMessage payloads without making live Telegram requests."""

	def test_send_message_sends_required_and_optional_fields(self) -> None:
		"""Send chat ID and text, adding parse mode only when supplied."""
		response = MagicMock()
		response.status_code = 200
		response.json.return_value = {"ok": True, "result": {"message_id": 1}}
		with (
			patch.object(telegram_service.requests, "post", return_value=response) as post,
			patch.object(telegram_service, "get_telegram_bot_token", return_value="bot-token"),
			patch.object(telegram_service.frappe, "logger"),
		):
			result = telegram_service.send_message(12345, "hello", parse_mode="Markdown")

		self.assertEqual(result["ok"], True)
		post.assert_called_once_with(
			"https://api.telegram.org/botbot-token/sendMessage",
			data={"chat_id": 12345, "text": "hello", "parse_mode": "Markdown"},
			timeout=SEND_MESSAGE_TIMEOUT,
		)
		response.raise_for_status.assert_called_once_with()

	def test_send_message_omits_parse_mode_when_not_supplied(self) -> None:
		"""Keep the transport payload minimal when parse mode is absent."""
		response = MagicMock()
		response.status_code = 200
		response.json.return_value = {"ok": True}
		with (
			patch.object(telegram_service.requests, "post", return_value=response) as post,
			patch.object(telegram_service, "get_telegram_bot_token", return_value="bot-token"),
			patch.object(telegram_service.frappe, "logger"),
		):
			telegram_service.send_message("chat", "hello")

		self.assertNotIn("parse_mode", post.call_args.kwargs["data"])
