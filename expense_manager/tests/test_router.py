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

	def test_addexpense_command_is_registered(self) -> None:
		"""/addexpense command is registered and routes to handle_addexpense."""
		self.assertIn("addexpense", router.COMMAND_HANDLERS)
		response = router.route_update({"message": {"text": "/addexpense lunch 250"}})
		self.assertIsNotNone(response)

	def test_free_text_routes_to_handler(self) -> None:
		"""Free text (no leading /) routes to the text expense handler, not unknown."""
		response = router.route_update({"message": {"text": "lunch 250"}})
		self.assertIsNotNone(response)
		self.assertNotIn("don't recognise", response)

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

	def test_domain_error_message_is_surfaced(self) -> None:
		"""Known business errors reach the user with their real message."""
		from expense_manager.services.exceptions import TelegramAlreadyLinkedError

		def _boom(_update):
			raise TelegramAlreadyLinkedError(
				"This user already has a linked Telegram account."
			)

		with patch.dict(router.COMMAND_HANDLERS, {"boom": _boom}):
			response = router.route_update({"message": {"text": "/boom"}})

		self.assertEqual(
			response,
			"This user already has a linked Telegram account.",
		)

	def test_unexpected_error_returns_generic_message(self) -> None:
		"""Non-domain exceptions keep the generic fallback message."""
		def _boom(_update):
			raise ValueError("internal failure")

		with patch.dict(router.COMMAND_HANDLERS, {"boom": _boom}):
			response = router.route_update({"message": {"text": "/boom"}})

		self.assertEqual(response, "Sorry, something went wrong. Please try again later.")
