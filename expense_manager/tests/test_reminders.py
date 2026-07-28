"""Unit tests for the daily reminders scheduler and its service-layer message builders."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from expense_manager.jobs import reminders
from expense_manager.services.report_service import ReportService
from expense_manager.services.pocket_money_service import PocketMoneyService


# ------------------------------------------------------------------
# _collect_reminders
# ------------------------------------------------------------------

class TestCollectReminders(TestCase):
	"""Verify that _collect_reminders aggregates messages from all services."""

	@patch.object(PocketMoneyService, "build_low_balance_messages", return_value=[])
	@patch.object(ReportService, "build_monthly_summary_message", return_value=None)
	@patch.object(ReportService, "build_weekly_summary_message", return_value=None)
	@patch.object(ReportService, "build_no_expenses_today_message", return_value=None)
	def test_returns_empty_when_no_reminders(self, *_mocks):
		result = reminders._collect_reminders("user@example.com")
		self.assertEqual(result, [])

	@patch.object(PocketMoneyService, "build_low_balance_messages", return_value=[])
	@patch.object(ReportService, "build_monthly_summary_message", return_value="Monthly total: 500")
	@patch.object(ReportService, "build_weekly_summary_message", return_value=None)
	@patch.object(ReportService, "build_no_expenses_today_message", return_value="No expenses today")
	def test_collects_multiple_messages(self, *_mocks):
		result = reminders._collect_reminders("user@example.com")
		self.assertIn("No expenses today", result)
		self.assertIn("Monthly total: 500", result)
		self.assertEqual(len(result), 2)

	@patch.object(PocketMoneyService, "build_low_balance_messages", return_value=["Low balance!"])
	@patch.object(ReportService, "build_monthly_summary_message", return_value=None)
	@patch.object(ReportService, "build_weekly_summary_message", return_value=None)
	@patch.object(ReportService, "build_no_expenses_today_message", return_value=None)
	def test_includes_low_balance_messages(self, *_mocks):
		result = reminders._collect_reminders("user@example.com")
		self.assertEqual(result, ["Low balance!"])


# ------------------------------------------------------------------
# run_reminders
# ------------------------------------------------------------------

class TestRunReminders(TestCase):
	"""Verify the scheduler dispatches messages for each linked user."""

	@patch.object(reminders, "send_message")
	@patch.object(reminders, "_collect_reminders", return_value=["msg1", "msg2"])
	@patch.object(reminders, "TelegramLinkService")
	@patch.object(reminders, "logger")
	def test_sends_all_messages(self, mock_logger, mock_link_service, _collect, mock_send):
		mock_link_service.list_links.return_value = [
			{"user": "user1", "telegram_user_id": "111"},
		]
		reminders.run_reminders()
		self.assertEqual(mock_send.call_count, 2)

	@patch.object(reminders, "send_message")
	@patch.object(reminders, "_collect_reminders", return_value=[])
	@patch.object(reminders, "TelegramLinkService")
	@patch.object(reminders, "logger")
	def test_skips_when_no_messages(self, mock_logger, mock_link_service, _collect, mock_send):
		mock_link_service.list_links.return_value = [
			{"user": "user1", "telegram_user_id": "111"},
		]
		reminders.run_reminders()
		mock_send.assert_not_called()

	@patch.object(reminders, "send_message", side_effect=Exception("network error"))
	@patch.object(reminders, "_collect_reminders", return_value=["msg1"])
	@patch.object(reminders, "TelegramLinkService")
	@patch.object(reminders, "logger")
	def test_handles_send_failure(self, mock_logger, mock_link_service, _collect, mock_send):
		mock_link_service.list_links.return_value = [
			{"user": "user1", "telegram_user_id": "111"},
		]
		reminders.run_reminders()
		mock_send.assert_called_once()

	@patch.object(reminders, "send_message")
	@patch.object(reminders, "_collect_reminders", return_value=["msg1"])
	@patch.object(reminders, "TelegramLinkService")
	@patch.object(reminders, "logger")
	def test_skips_incomplete_links(self, mock_logger, mock_link_service, _collect, mock_send):
		mock_link_service.list_links.return_value = [
			{"user": "user1", "telegram_user_id": None},
			{"user": None, "telegram_user_id": "222"},
		]
		reminders.run_reminders()
		mock_send.assert_not_called()


# ------------------------------------------------------------------
# ReportService notification message builders
# ------------------------------------------------------------------

class TestBuildNoExpensesTodayMessage(TestCase):

	@patch.object(ReportService, "_get_expenses", return_value=[{"name": "e1"}])
	def test_returns_none_when_expenses_exist(self, _mock):
		self.assertIsNone(ReportService.build_no_expenses_today_message("user1"))

	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_returns_message_when_no_expenses(self, _mock):
		msg = ReportService.build_no_expenses_today_message("user1")
		self.assertIn("haven't logged", msg)


class TestBuildWeeklySummaryMessage(TestCase):

	@patch.object(ReportService, "get_category_breakdown", return_value=[])
	def test_returns_none_when_no_data(self, _mock):
		self.assertIsNone(ReportService.build_weekly_summary_message("user1"))

	@patch.object(ReportService, "get_category_breakdown", return_value=[
		{"category_name": "Food", "total_amount": 500},
		{"category_name": "Transport", "total_amount": 200},
	])
	def test_returns_formatted_summary(self, _mock):
		msg = ReportService.build_weekly_summary_message("user1")
		self.assertIn("Weekly summary", msg)
		self.assertIn("Food", msg)
		self.assertIn("700", msg)


class TestBuildMonthlySummaryMessage(TestCase):

	@patch.object(ReportService, "get_category_breakdown", return_value=[])
	def test_returns_none_when_no_data(self, _mock):
		self.assertIsNone(ReportService.build_monthly_summary_message("user1"))

	@patch.object(ReportService, "get_category_breakdown", return_value=[
		{"category_name": "Bills", "total_amount": 1200},
	])
	def test_returns_formatted_summary(self, _mock):
		msg = ReportService.build_monthly_summary_message("user1")
		self.assertIn("Monthly summary", msg)
		self.assertIn("Bills", msg)


# ------------------------------------------------------------------
# PocketMoneyService low-balance message builder
# ------------------------------------------------------------------

class TestBuildLowBalanceMessages(TestCase):

	@patch.object(PocketMoneyService, "get_balance", return_value=None)
	@patch("expense_manager.services.pocket_money_service.DependentService")
	def test_returns_empty_when_no_balances(self, mock_ds, _mock_bal):
		mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
		self.assertEqual(PocketMoneyService.build_low_balance_messages("user1"), [])

	@patch.object(PocketMoneyService, "get_balance", return_value={
		"allocated_amount": 1000,
		"remaining_amount": 800,
	})
	@patch("expense_manager.services.pocket_money_service.DependentService")
	def test_returns_empty_when_balance_high(self, mock_ds, _mock_bal):
		mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
		self.assertEqual(PocketMoneyService.build_low_balance_messages("user1"), [])

	@patch.object(PocketMoneyService, "get_balance", return_value={
		"allocated_amount": 1000,
		"remaining_amount": 100,
	})
	@patch("expense_manager.services.pocket_money_service.DependentService")
	def test_returns_message_when_balance_low(self, mock_ds, _mock_bal):
		mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
		msgs = PocketMoneyService.build_low_balance_messages("user1")
		self.assertEqual(len(msgs), 1)
		self.assertIn("running low", msgs[0])
		self.assertIn("Son", msgs[0])
