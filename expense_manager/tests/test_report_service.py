"""Unit tests for ReportService."""

from unittest.mock import MagicMock, patch

from expense_manager.services.exceptions import InvalidReportDateRangeError
from expense_manager.services.report_service import ReportService
from expense_manager.tests.base import SAMPLE_EXPENSE, SAMPLE_USER, ServiceTestCase


class TestValidateDateRange(ServiceTestCase):
	def test_none_dates_are_valid(self):
		ReportService._validate_date_range(None, None)

	def test_end_before_start_raises(self):
		with self.assertRaises(InvalidReportDateRangeError):
			ReportService._validate_date_range("2026-07-31", "2026-07-01")

	def test_same_dates_are_valid(self):
		ReportService._validate_date_range("2026-07-15", "2026-07-15")

	def test_end_after_start_is_valid(self):
		ReportService._validate_date_range("2026-07-01", "2026-07-31")


class TestCalculateTotals(ServiceTestCase):
	def test_empty_list(self):
		result = ReportService._calculate_totals([])
		self.assertEqual(result["total_amount"], 0)
		self.assertEqual(result["expense_count"], 0)
		self.assertEqual(result["average_expense"], 0)

	def test_single_expense(self):
		expenses = [{"amount": 250.0}]
		result = ReportService._calculate_totals(expenses)
		self.assertEqual(result["total_amount"], 250.0)
		self.assertEqual(result["expense_count"], 1)
		self.assertEqual(result["average_expense"], 250.0)

	def test_multiple_expenses(self):
		expenses = [{"amount": 100.0}, {"amount": 200.0}, {"amount": 300.0}]
		result = ReportService._calculate_totals(expenses)
		self.assertEqual(result["total_amount"], 600.0)
		self.assertEqual(result["expense_count"], 3)
		self.assertEqual(result["average_expense"], 200.0)


class TestGroupByCategory(ServiceTestCase):
	def test_empty_list(self):
		self.assertEqual(ReportService._group_by_category([]), {})

	def test_groups_correctly(self):
		expenses = [
			{"category": "Food", "amount": 100.0},
			{"category": "Transport", "amount": 50.0},
			{"category": "Food", "amount": 200.0},
		]
		result = ReportService._group_by_category(expenses)
		self.assertEqual(len(result), 2)
		self.assertEqual(result["Food"]["total_amount"], 300.0)
		self.assertEqual(result["Food"]["expense_count"], 2)
		self.assertEqual(result["Transport"]["total_amount"], 50.0)
		self.assertEqual(result["Transport"]["expense_count"], 1)


class TestGroupByMonth(ServiceTestCase):
	def test_empty_list(self):
		self.assertEqual(ReportService._group_by_month([]), {})

	def test_groups_by_month(self):
		expenses = [
			{"expense_date": "2026-07-01", "amount": 100.0},
			{"expense_date": "2026-07-15", "amount": 200.0},
			{"expense_date": "2026-08-05", "amount": 50.0},
		]
		result = ReportService._group_by_month(expenses)
		self.assertEqual(result["2026-07"], 300.0)
		self.assertEqual(result["2026-08"], 50.0)


class TestGetExpenseSummary(ServiceTestCase):
	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_empty_expenses(self, _mock_exp):
		result = ReportService.get_expense_summary(SAMPLE_USER)
		self.assertEqual(result["total_amount"], 0)
		self.assertEqual(result["expense_count"], 0)
		self.assertEqual(result["average_expense"], 0)

	@patch.object(ReportService, "_get_expenses")
	def test_with_expenses(self, mock_exp):
		mock_exp.return_value = [{"amount": 100.0}, {"amount": 200.0}]
		result = ReportService.get_expense_summary(SAMPLE_USER)
		self.assertEqual(result["total_amount"], 300.0)
		self.assertEqual(result["expense_count"], 2)

	def test_invalid_date_range_raises(self):
		with self.assertRaises(InvalidReportDateRangeError):
			ReportService.get_expense_summary(SAMPLE_USER, date_from="2026-07-31", date_to="2026-07-01")


class TestGetBudgetSummary(ServiceTestCase):
	@patch.object(
		ReportService,
		"_category_name_lookup",
		return_value={"cat-food-001": {"category_name": "Food", "icon": ""}},
	)
	@patch("expense_manager.services.report_service.BudgetService.get_budget_usage")
	@patch("expense_manager.services.report_service.BudgetService.list_budgets")
	def test_empty_budgets(self, mock_list, mock_usage, _mock_lookup):
		mock_list.return_value = []
		result = ReportService.get_budget_summary(SAMPLE_USER)
		self.assertEqual(result, [])

	@patch.object(
		ReportService,
		"_category_name_lookup",
		return_value={"cat-food-001": {"category_name": "Food", "icon": ""}},
	)
	@patch("expense_manager.services.report_service.BudgetService.get_budget_usage")
	@patch("expense_manager.services.report_service.BudgetService.list_budgets")
	def test_with_usage(self, mock_list, mock_usage, _mock_lookup):
		mock_list.return_value = [{"category": "cat-food-001"}]
		mock_usage.return_value = {
			"allocated_amount": 5000,
			"spent_amount": 3000,
			"remaining_amount": 2000,
			"pct_used": 60.0,
			"is_overspent": False,
		}
		result = ReportService.get_budget_summary(SAMPLE_USER)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["category_name"], "Food")
		self.assertEqual(result[0]["allocated_amount"], 5000)

	@patch.object(ReportService, "_category_name_lookup", return_value={})
	@patch("expense_manager.services.report_service.BudgetService.get_budget_usage", return_value=None)
	@patch("expense_manager.services.report_service.BudgetService.list_budgets")
	def test_skips_none_usage(self, mock_list, _mock_usage, _mock_lookup):
		mock_list.return_value = [{"category": "cat-food-001"}]
		result = ReportService.get_budget_summary(SAMPLE_USER)
		self.assertEqual(result, [])


class TestGetPocketMoneySummary(ServiceTestCase):
	@patch("expense_manager.services.report_service.PocketMoneyService.get_balance", return_value=None)
	@patch("expense_manager.services.report_service.DependentService.list_dependents")
	def test_empty_dependents(self, mock_dep, _mock_bal):
		mock_dep.return_value = []
		result = ReportService.get_pocket_money_summary(SAMPLE_USER)
		self.assertEqual(result, [])

	@patch("expense_manager.services.report_service.PocketMoneyService.get_balance")
	@patch("expense_manager.services.report_service.DependentService.list_dependents")
	def test_with_balance(self, mock_dep, mock_bal):
		mock_dep.return_value = [{"name": "dep-001", "dependent_name": "Son"}]
		mock_bal.return_value = {
			"allocated_amount": 2000,
			"spent_amount": 500,
			"carry_forward": 0,
			"remaining_amount": 1500,
		}
		result = ReportService.get_pocket_money_summary(SAMPLE_USER)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["dependent_name"], "Son")
		self.assertEqual(result[0]["remaining_amount"], 1500)

	@patch("expense_manager.services.report_service.PocketMoneyService.get_balance")
	@patch("expense_manager.services.report_service.DependentService.list_dependents")
	def test_total_savings_includes_remaining(self, mock_dep, mock_bal):
		mock_dep.return_value = [{"name": "dep-001", "dependent_name": "Son"}]
		mock_bal.return_value = {
			"allocated_amount": 2000,
			"spent_amount": 500,
			"carry_forward": 0,
			"remaining_amount": 1500,
			"total_savings": 750,
		}
		result = ReportService.get_pocket_money_summary(SAMPLE_USER)
		self.assertEqual(result[0]["total_savings"], 2250)

	@patch("expense_manager.services.report_service.PocketMoneyService.get_balance")
	@patch("expense_manager.services.report_service.DependentService.list_dependents")
	def test_dependent_filter_narrows_results(self, mock_dep, mock_bal):
		mock_dep.return_value = [
			{"name": "dep-001", "dependent_name": "Son"},
			{"name": "dep-002", "dependent_name": "Daughter"},
		]
		mock_bal.return_value = {
			"allocated_amount": 0,
			"spent_amount": 0,
			"carry_forward": 0,
			"remaining_amount": 0,
		}
		result = ReportService.get_pocket_money_summary(SAMPLE_USER, dependent="dep-002")
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0]["dependent"], "dep-002")


class TestGetCategoryBreakdown(ServiceTestCase):
	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_empty_expenses(self, _mock_exp):
		result = ReportService.get_category_breakdown(SAMPLE_USER)
		self.assertEqual(result, [])

	@patch.object(
		ReportService, "_category_name_lookup", return_value={"Food": {"category_name": "Food", "icon": ""}}
	)
	@patch.object(ReportService, "_get_expenses")
	def test_groups_and_sorts(self, mock_exp, _mock_lookup):
		mock_exp.return_value = [
			{"category": "Food", "amount": 300.0},
			{"category": "Transport", "amount": 100.0},
			{"category": "Food", "amount": 200.0},
		]
		result = ReportService.get_category_breakdown(SAMPLE_USER)
		self.assertEqual(len(result), 2)
		self.assertEqual(result[0]["category"], "Food")
		self.assertEqual(result[0]["total_amount"], 500.0)
		self.assertEqual(result[0]["expense_count"], 2)
		self.assertAlmostEqual(result[0]["percentage_of_total"], 83.33, places=1)
		self.assertEqual(result[1]["category"], "Transport")
		self.assertAlmostEqual(result[1]["percentage_of_total"], 16.67, places=1)

	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_category_filter_passed_to_expenses(self, mock_exp):
		ReportService.get_category_breakdown(SAMPLE_USER, category="cat-food-001")
		_, kwargs = mock_exp.call_args
		self.assertEqual(kwargs.get("category"), "cat-food-001")


class TestGetMonthlyReport(ServiceTestCase):
	@patch.object(ReportService, "_get_expenses")
	def test_returns_12_months(self, mock_exp):
		mock_exp.return_value = [
			{"expense_date": "2026-03-10", "amount": 500.0},
			{"expense_date": "2026-03-20", "amount": 300.0},
		]
		result = ReportService.get_monthly_report(SAMPLE_USER, year=2026)
		self.assertEqual(len(result), 12)
		march = next(r for r in result if r["month"] == "2026-03")
		self.assertEqual(march["total_amount"], 800.0)
		jan = next(r for r in result if r["month"] == "2026-01")
		self.assertEqual(jan["total_amount"], 0)

	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_empty_year(self, _mock_exp):
		result = ReportService.get_monthly_report(SAMPLE_USER, year=2026)
		self.assertTrue(all(r["total_amount"] == 0 for r in result))


class TestGetSpendingTrend(ServiceTestCase):
	def test_months_zero_raises(self):
		with self.assertRaises(InvalidReportDateRangeError):
			ReportService.get_spending_trend(SAMPLE_USER, months=0)

	def test_months_negative_raises(self):
		with self.assertRaises(InvalidReportDateRangeError):
			ReportService.get_spending_trend(SAMPLE_USER, months=-1)

	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_returns_months_entries(self, _mock_exp):
		result = ReportService.get_spending_trend(SAMPLE_USER, months=3)
		self.assertEqual(len(result), 3)
		self.assertTrue(all("month" in r for r in result))

	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_category_filter_passed_to_expenses(self, mock_exp):
		ReportService.get_spending_trend(SAMPLE_USER, months=3, category="cat-food-001")
		_, kwargs = mock_exp.call_args
		self.assertEqual(kwargs.get("category"), "cat-food-001")


class TestGetDashboardSummary(ServiceTestCase):
	@patch("expense_manager.services.report_service.ExpenseService.attach_dependent_names")
	@patch.object(ReportService, "_category_name_lookup", return_value={})
	@patch("expense_manager.services.report_service.ExpenseService.list_expenses", return_value=[])
	@patch.object(ReportService, "_get_expenses", return_value=[])
	@patch.object(ReportService, "get_budget_summary", return_value=[])
	def test_filters_passed_to_queries(self, _mock_budget, mock_exp, _mock_list, _mock_lookup, _mock_attach):
		ReportService.get_dashboard_summary(
			SAMPLE_USER,
			dependent="dep-001",
			category="cat-food-001",
			date_from="2026-07-01",
			date_to="2026-07-31",
		)
		_, kwargs = mock_exp.call_args_list[0]
		self.assertEqual(kwargs.get("dependent"), "dep-001")
		self.assertEqual(kwargs.get("category"), "cat-food-001")
		self.assertEqual(kwargs.get("date_from"), "2026-07-01")
		self.assertEqual(kwargs.get("date_to"), "2026-07-31")


class TestGetDependentReport(ServiceTestCase):
	@patch("expense_manager.services.report_service.PocketMoneyService.get_balance")
	@patch("expense_manager.services.report_service.DependentService.get_dependent")
	def test_returns_composed_report(self, mock_dep, mock_bal):
		mock_dep.return_value = MagicMock(name="dep-001", dependent_name="Son")
		mock_bal.return_value = {"remaining_amount": 1000}
		result = ReportService.get_dependent_report(SAMPLE_USER, "dep-001")
		self.assertIn("dependent", result)
		self.assertIn("pocket_money", result)
		self.assertIn("expense_summary", result)
		self.assertIn("category_breakdown", result)


class TestBuildNoExpensesTodayMessage(ServiceTestCase):
	@patch.object(ReportService, "_get_expenses", return_value=[])
	def test_returns_nudge_when_empty(self, _mock_exp):
		msg = ReportService.build_no_expenses_today_message(SAMPLE_USER)
		self.assertIn("haven't logged", msg)

	@patch.object(ReportService, "_get_expenses", return_value=[{"amount": 100}])
	def test_returns_none_when_expenses_exist(self, _mock_exp):
		msg = ReportService.build_no_expenses_today_message(SAMPLE_USER)
		self.assertIsNone(msg)


class TestBuildWeeklySummaryMessage(ServiceTestCase):
	@patch.object(ReportService, "get_category_breakdown", return_value=[])
	def test_returns_none_when_empty(self, _mock_bd):
		msg = ReportService.build_weekly_summary_message(SAMPLE_USER)
		self.assertIsNone(msg)

	@patch.object(ReportService, "get_category_breakdown")
	def test_returns_formatted_summary(self, mock_bd):
		mock_bd.return_value = [
			{"category_name": "Food", "total_amount": 500.0},
			{"category_name": "Transport", "total_amount": 200.0},
		]
		msg = ReportService.build_weekly_summary_message(SAMPLE_USER)
		self.assertIn("Weekly summary", msg)
		self.assertIn("Food", msg)
		self.assertIn("700", msg)


class TestBuildMonthlySummaryMessage(ServiceTestCase):
	@patch.object(ReportService, "get_category_breakdown", return_value=[])
	def test_returns_none_when_empty(self, _mock_bd):
		msg = ReportService.build_monthly_summary_message(SAMPLE_USER)
		self.assertIsNone(msg)

	@patch.object(ReportService, "get_category_breakdown")
	def test_returns_formatted_summary(self, mock_bd):
		mock_bd.return_value = [
			{"category_name": "Food", "total_amount": 1000.0},
		]
		msg = ReportService.build_monthly_summary_message(SAMPLE_USER)
		self.assertIn("Monthly summary", msg)
		self.assertIn("Food", msg)
		self.assertIn("1000", msg)
