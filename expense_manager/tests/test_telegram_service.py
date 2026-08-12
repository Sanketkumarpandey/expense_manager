"""Unit tests for the minimal Telegram sendMessage transport and TelegramService orchestration."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from expense_manager.services.exceptions import PocketMoneyExceededError, TelegramNotLinkedError
from expense_manager.telegram.services import telegram_service
from expense_manager.telegram.services.telegram_service import TelegramService
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


class TestTelegramServiceListCategories(TestCase):
	"""Verify TelegramService.list_categories resolves identity and calls CategoryService correctly."""

	def setUp(self) -> None:
		self.telegram_user_id = "123456789"
		self.guardian_email = "guardian@example.com"
		self.dependent_name = "dep-son-001"

	def _patch_identity_resolution(self, is_dependent: bool = False):
		"""Patch identity resolution to return a known identity."""
		identity = {
			"owner_user": self.guardian_email,
			"dependent": self.dependent_name if is_dependent else None,
			"is_dependent": is_dependent,
		}
		return patch.object(
			TelegramService,
			"_resolve_identity_or_error",
			return_value=(identity, None),
		)

	def test_guardian_gets_own_categories(self):
		"""Guardian's /categories should fetch all guardian-owned shared categories."""
		mock_categories = [{"name": "cat-1", "category_name": "Food"}]
		with (
			self._patch_identity_resolution(is_dependent=False),
			patch(
				"expense_manager.telegram.services.telegram_service.CategoryService.list_categories",
				return_value=mock_categories,
			) as mock_list,
		):
			result = TelegramService.list_categories(self.telegram_user_id)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"], mock_categories)
		mock_list.assert_called_once_with(self.guardian_email, active_only=True)

	def test_dependent_gets_scoped_categories(self):
		"""Dependent's /categories should resolve through their allowed_categories."""
		mock_categories = [{"name": "cat-1", "category_name": "Food"}]
		with (
			self._patch_identity_resolution(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_allowed_categories",
				return_value=mock_categories,
			) as mock_list,
		):
			result = TelegramService.list_categories(self.telegram_user_id)

		self.assertTrue(result["success"])
		self.assertEqual(result["data"], mock_categories)
		mock_list.assert_called_once_with(self.guardian_email, self.dependent_name, active_only=True)

	def test_unlinked_user_gets_error(self):
		"""Unlinked Telegram user should get an error message, not categories."""
		with patch.object(
			TelegramService,
			"_resolve_identity_or_error",
			return_value=(None, {"success": False, "message": "not linked"}),
		):
			result = TelegramService.list_categories(self.telegram_user_id)

		self.assertFalse(result["success"])
		self.assertEqual(result["message"], "not linked")


class TestBuildExpensesDisplay(TestCase):
	"""Verify TelegramService.build_expenses_display groups correctly."""

	def setUp(self) -> None:
		self.telegram_user_id = "123456789"
		self.guardian_email = "guardian@example.com"
		self.dependent_name = "dep-son-001"

	def _patch_identity(self, is_dependent: bool = False):
		identity = {
			"owner_user": self.guardian_email,
			"dependent": self.dependent_name if is_dependent else None,
			"is_dependent": is_dependent,
		}
		return patch.object(
			TelegramService,
			"_resolve_identity_or_error",
			return_value=(identity, None),
		)

	def _make_expense(self, cat_name: str, amount: float, category: str | None = None):
		return {"category": category or cat_name.lower(), "category_name": cat_name, "amount": amount}

	def test_dependent_view_flat(self):
		expenses = [self._make_expense("Food", 450), self._make_expense("Travel", 120)]
		with (
			self._patch_identity(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.get_recent_expenses",
				return_value=expenses,
			),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_allowed_categories",
				return_value=[
					{"name": "food", "category_name": "Food"},
					{"name": "travel", "category_name": "Travel"},
				],
			),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertIn("Your recent expenses:", result)
		self.assertIn("Food", result)
		self.assertIn("₹450", result)
		self.assertIn("Total:", result)
		self.assertNotIn("👤", result)

	def test_dependent_view_no_expenses(self):
		with (
			self._patch_identity(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.get_recent_expenses",
				return_value=[],
			),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertEqual(result, "You don't have any recent expenses.")

	def test_guardian_own_only_collapses(self):
		expenses = [self._make_expense("Food", 450)]
		with (
			self._patch_identity(is_dependent=False),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.get_recent_expenses",
				side_effect=lambda _o, dependent=None, limit=10: expenses
				if dependent == ["is", "not set"]
				else [],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.CategoryService.list_categories",
				return_value=[{"name": "food", "category_name": "Food"}],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_dependents",
				return_value=[],
			),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertIn("Your recent expenses:", result)
		self.assertIn("| Food | \u20b9450", result)
		self.assertNotIn("👤", result)

	def test_guardian_group_dependents(self):
		own = [self._make_expense("Food", 450)]
		dep_exp = [self._make_expense("Travel", 120)]

		def _fake_get_recent(owner_user, dependent=None, limit=10):
			if dependent == ["is", "not set"]:
				return own
			if dependent == self.dependent_name:
				return dep_exp
			return []

		with (
			self._patch_identity(is_dependent=False),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.get_recent_expenses",
				side_effect=_fake_get_recent,
			),
			patch(
				"expense_manager.telegram.services.telegram_service.CategoryService.list_categories",
				return_value=[
					{"name": "food", "category_name": "Food"},
					{"name": "travel", "category_name": "Travel"},
				],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_dependents",
				return_value=[{"name": self.dependent_name, "dependent_name": "Aarav"}],
			),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertIn("Your recent expenses:", result)
		self.assertIn("👤 You", result)
		self.assertIn("| Food | \u20b9450", result)
		self.assertIn("👤 Aarav", result)
		self.assertIn("| Travel | \u20b9120", result)
		self.assertIn("Grand total", result)
		self.assertIn("₹570", result)

	def test_guardian_no_expenses(self):
		def _fake_get_recent(owner_user, dependent=None, limit=10):
			return []

		with (
			self._patch_identity(is_dependent=False),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.get_recent_expenses",
				side_effect=_fake_get_recent,
			),
			patch(
				"expense_manager.telegram.services.telegram_service.CategoryService.list_categories",
				return_value=[],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_dependents",
				return_value=[],
			),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertEqual(result, "You don't have any recent expenses.")

	def test_unlinked_user_gets_error(self):
		with patch.object(
			TelegramService,
			"_resolve_identity_or_error",
			return_value=(None, {"success": False, "message": "not linked"}),
		):
			result = TelegramService.build_expenses_display(self.telegram_user_id)
		self.assertEqual(result, "not linked")


class TestTelegramServiceCreateExpenseHardBlock(TestCase):
	"""TelegramService.create_expense enforces the pocket-money hard block
	for dependents before calling ExpenseService.create_expense."""

	def setUp(self) -> None:
		self.telegram_user_id = "7927311707"
		self.guardian_email = "guardian@example.com"
		self.dependent_name = "dep-son-001"

	def _patch_identity(self, is_dependent: bool):
		identity = {
			"owner_user": self.guardian_email,
			"dependent": self.dependent_name if is_dependent else None,
			"is_dependent": is_dependent,
		}
		return patch.object(
			TelegramService,
			"_resolve_identity_or_error",
			return_value=(identity, None),
		)

	def test_dependent_expense_enforces_block(self):
		data = {"category": "cat-food-dep-001", "amount": 200, "expense_date": "2026-07-27"}
		with (
			self._patch_identity(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_allowed_categories",
				return_value=[{"name": "cat-food-dep-001", "category_name": "Food"}],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.PocketMoneyService.enforce_available_balance"
			) as mock_enforce,
			patch("expense_manager.telegram.services.telegram_service.ExpenseService.create_expense"),
			patch.object(TelegramService, "_get_overspend_warning", return_value=""),
		):
			result = TelegramService.create_expense(self.telegram_user_id, data)

		self.assertTrue(result["success"])
		mock_enforce.assert_called_once_with(self.guardian_email, self.dependent_name, 200.0)

	def test_dependent_excluded_category_rejected(self):
		"""A dependent cannot log an expense against a category outside their
		allowed_categories, even when pocket money is available."""
		data = {"category": "cat-food-001", "amount": 200, "expense_date": "2026-07-27"}
		with (
			self._patch_identity(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.DependentService.list_allowed_categories",
				return_value=[{"name": "cat-gym-001", "category_name": "Gym"}],
			),
			patch(
				"expense_manager.telegram.services.telegram_service.PocketMoneyService.enforce_available_balance"
			),
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.create_expense"
			) as mock_create,
		):
			result = TelegramService.create_expense(self.telegram_user_id, data)

		self.assertFalse(result["success"])
		self.assertIn("not allowed", result["message"])
		mock_create.assert_not_called()

	def test_blocked_expense_returns_failure(self):
		data = {"category": "cat-food-dep-001", "amount": 500, "expense_date": "2026-07-27"}
		with (
			self._patch_identity(is_dependent=True),
			patch(
				"expense_manager.telegram.services.telegram_service.PocketMoneyService.enforce_available_balance",
				side_effect=PocketMoneyExceededError(
					"Not enough pocket money: ₹0.0 available but this costs ₹500.0."
				),
			) as mock_enforce,
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.create_expense"
			) as mock_create,
		):
			result = TelegramService.create_expense(self.telegram_user_id, data)

		self.assertFalse(result["success"])
		self.assertIn("Not enough pocket money", result["message"])
		mock_enforce.assert_called_once()
		mock_create.assert_not_called()

	def test_guardian_expense_skips_block(self):
		data = {"category": "cat-food-001", "amount": 200, "expense_date": "2026-07-27"}
		with (
			self._patch_identity(is_dependent=False),
			patch(
				"expense_manager.telegram.services.telegram_service.PocketMoneyService.enforce_available_balance"
			) as mock_enforce,
			patch(
				"expense_manager.telegram.services.telegram_service.ExpenseService.create_expense"
			) as mock_create,
			patch.object(TelegramService, "_get_overspend_warning", return_value=""),
		):
			TelegramService.create_expense(self.telegram_user_id, data)

		mock_enforce.assert_not_called()
		mock_create.assert_called_once()
