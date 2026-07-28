"""Unit tests for command extraction and Telegram handler dispatch."""

from unittest import TestCase
from unittest.mock import patch

from expense_manager.telegram import router


class TestTelegramRouter(TestCase):
	"""Verify supported commands, fallback behavior, and ignored update types."""

	def setUp(self) -> None:
		"""Silence structured router logs during unit tests."""
		self.logger_patch = patch.object(router.frappe, "logger")
		self.logger_patch.start()

	def tearDown(self) -> None:
		"""Restore Frappe logging after each routing test."""
		self.logger_patch.stop()

	def test_start_help_link_and_unlink_dispatch(self) -> None:
		"""Dispatch each supported command to its registered handler."""
		updates = {
			"start": {"message": {"text": "/START@expense_bot"}},
			"help": {"message": {"text": "/help"}},
			"link": {"message": {"text": "/link now"}},
			"unlink": {"message": {"text": "/unlink"}},
		}

		self.assertIn("start", router.COMMAND_HANDLERS)
		self.assertIn("help", router.COMMAND_HANDLERS)
		self.assertIn("link", router.COMMAND_HANDLERS)
		self.assertIn("unlink", router.COMMAND_HANDLERS)
		self.assertIn("Expense Manager", router.route_update(updates["start"]))
		self.assertIn("Available commands", router.route_update(updates["help"]))
		self.assertIsNotNone(router.route_update(updates["link"]))
		self.assertIsNotNone(router.route_update(updates["unlink"]))

	def test_unknown_command_uses_friendly_fallback(self) -> None:
		"""Route unsupported commands to the unknown-command handler."""
		response = router.route_update({"message": {"text": "/unsupported"}})

		self.assertIsNotNone(response)
		self.assertIn("/help", response)

	def test_malformed_update_is_ignored(self) -> None:
		"""Ignore non-dictionary and incomplete updates without raising to a user."""
		self.assertIsNone(router.route_update(None))
		self.assertIsNone(router.route_update({"message": "invalid"}))
		self.assertIsNone(router.route_update({"message": {"text": ""}}))

	def test_unsupported_update_type_is_ignored(self) -> None:
		"""Ignore callback queries; voice messages are dispatched to handle_voice."""
		self.assertIsNone(router.route_update({"callback_query": {"data": "/help"}}))
		voice_response = router.route_update({"message": {"voice": {"file_id": "file"}}})
		self.assertIsNotNone(voice_response)
