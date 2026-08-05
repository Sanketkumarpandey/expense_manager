"""Unit tests for BudgetService."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.exceptions import (
    BudgetAlreadyExistsError,
    BudgetNotFoundError,
    InvalidBudgetPeriodError,
    InvalidBudgetAmountError,
    InvalidBudgetDateRangeError,
    InvalidAlertThresholdError,
)
from expense_manager.tests.base import ServiceTestCase, SAMPLE_USER, SAMPLE_USER_2, SAMPLE_BUDGET, SAMPLE_BUDGET_DEP, SAMPLE_DEPENDENT


class TestCreateBudget(ServiceTestCase):

    @patch.object(BudgetService, "_get_active_budget_for_category", return_value=None)
    @patch("expense_manager.services.budget_service.CategoryService.get_category")
    def test_create_success(self, _mock_cat, _mock_active):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 5000, "Monthly", "2026-07-01", "2026-07-31"
            )
            self.assertEqual(result.allocated_amount, 5000)

    @patch.object(BudgetService, "_get_active_budget_for_category", return_value={"name": "existing"})
    def test_create_duplicate_raises(self, _mock_active):
        with self.assertRaises(BudgetAlreadyExistsError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 5000, "Monthly", "2026-07-01", "2026-07-31"
            )

    def test_create_invalid_period_raises(self):
        with self.assertRaises(InvalidBudgetPeriodError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 5000, "Daily", "2026-07-01", "2026-07-31"
            )

    def test_create_zero_amount_raises(self):
        with self.assertRaises(InvalidBudgetAmountError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 0, "Monthly", "2026-07-01", "2026-07-31"
            )

    def test_create_negative_amount_raises(self):
        with self.assertRaises(InvalidBudgetAmountError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", -100, "Monthly", "2026-07-01", "2026-07-31"
            )

    def test_create_end_before_start_raises(self):
        with self.assertRaises(InvalidBudgetDateRangeError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 5000, "Monthly", "2026-07-31", "2026-07-01"
            )

    def test_create_invalid_threshold_raises(self):
        with self.assertRaises(InvalidAlertThresholdError):
            BudgetService.create_budget(
                SAMPLE_USER, "cat-food-001", 5000, "Monthly", "2026-07-01", "2026-07-31",
                alert_threshold_pct=150
            )


class TestGetBudget(ServiceTestCase):

    def test_get_success(self):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = BudgetService.get_budget(SAMPLE_USER, "bud-001")
            self.assertEqual(result.name, "bud-001")

    def test_get_not_found(self):
        with patch.object(frappe, "get_doc", side_effect=frappe.DoesNotExistError):
            with self.assertRaises(BudgetNotFoundError):
                BudgetService.get_budget(SAMPLE_USER, "nonexistent")

    def test_get_wrong_owner(self):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(BudgetNotFoundError):
                BudgetService.get_budget(SAMPLE_USER_2, "bud-001")


class TestUpdateBudget(ServiceTestCase):

    def test_update_amount(self):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            BudgetService.update_budget(SAMPLE_USER, "bud-001", allocated_amount=8000)
            self.assertEqual(doc.allocated_amount, 8000)
            doc.save.assert_called_once()


class TestDeleteBudget(ServiceTestCase):

    def test_delete_success(self):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            BudgetService.delete_budget(SAMPLE_USER, "bud-001")
            doc.delete.assert_called_once()


class TestArchiveRestore(ServiceTestCase):

    def test_archive(self):
        doc = self._make_doc(**SAMPLE_BUDGET)
        with patch.object(frappe, "get_doc", return_value=doc):
            BudgetService.archive_budget(SAMPLE_USER, "bud-001")
            self.assertFalse(doc.is_active)

    def test_restore(self):
        doc = self._make_doc(base=SAMPLE_BUDGET, is_active=0)
        with patch.object(frappe, "get_doc", return_value=doc):
            BudgetService.restore_budget(SAMPLE_USER, "bud-001")
            self.assertTrue(doc.is_active)


class TestListBudgets(ServiceTestCase):

    def test_list_returns_data(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_BUDGET]):
            result = BudgetService.list_budgets(SAMPLE_USER)
            self.assertEqual(len(result), 1)

    def test_list_active_only(self):
        with patch.object(frappe, "get_all", return_value=[]) as mock_get:
            BudgetService.list_budgets(SAMPLE_USER, active_only=True)
            filters = mock_get.call_args[1]["filters"]
            self.assertEqual(filters["is_active"], 1)


class TestBudgetUsage(ServiceTestCase):

    @patch.object(BudgetService, "get_budget")
    def test_usage_returns_none_when_no_budget(self, _mock_get):
        _mock_get.side_effect = BudgetNotFoundError
        result = BudgetService.get_budget_usage(SAMPLE_USER, "cat-food-001")
        self.assertIsNone(result)


class TestBuildAlertMessage(ServiceTestCase):

    def test_builds_message(self):
        usage = {
            "allocated_amount": 5000,
            "spent_amount": 4500,
            "pct_used": 90,
            "is_overspent": False,
        }
        msg = BudgetService.build_budget_alert_message("Food", usage)
        self.assertIn("Food", msg)
        self.assertIn("90", msg)


class TestCreateBudgetWithDependent(ServiceTestCase):

    @patch.object(BudgetService, "_get_active_budget_for_category", return_value=None)
    @patch("expense_manager.services.budget_service.CategoryService.get_category")
    def test_create_with_dependent(self, _mock_cat, _mock_active):
        doc = self._make_doc(**SAMPLE_BUDGET_DEP)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = BudgetService.create_budget(
                SAMPLE_USER, "cat-food-dep-001", 3000, "Monthly",
                "2026-07-01", "2026-07-31", dependent="dep-son-001"
            )
            self.assertEqual(result.dependent, "dep-son-001")


class TestGetBudgetWithDependent(ServiceTestCase):

    def test_get_with_dependent_success(self):
        doc = self._make_doc(**SAMPLE_BUDGET_DEP)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = BudgetService.get_budget(SAMPLE_USER, "bud-dep-001", dependent="dep-son-001")
            self.assertEqual(result.name, "bud-dep-001")

    def test_get_with_dependent_rejects_wrong_dependent(self):
        doc = self._make_doc(**SAMPLE_BUDGET_DEP)
        with patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(BudgetNotFoundError):
                BudgetService.get_budget(SAMPLE_USER, "bud-dep-001", dependent="dep-daughter-001")

    def test_get_without_dependent_rejects_dependent_budget(self):
        doc = self._make_doc(**SAMPLE_BUDGET_DEP)
        with patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(BudgetNotFoundError):
                BudgetService.get_budget(SAMPLE_USER, "bud-dep-001")


class TestRefreshBudgetWithDependent(ServiceTestCase):

    @patch.object(BudgetService, "_get_active_budget_for_category")
    @patch.object(BudgetService, "_calculate_spent_amount", return_value=500.0)
    def test_refresh_with_dependent(self, _mock_calc, _mock_active):
        doc = self._make_doc(**SAMPLE_BUDGET_DEP)
        _mock_active.return_value = doc
        BudgetService.refresh_budget(SAMPLE_USER, "cat-food-dep-001", dependent="dep-son-001")
        _mock_calc.assert_called_once()
        args, kwargs = _mock_calc.call_args
        self.assertEqual(kwargs.get("dependent"), "dep-son-001")

    @patch.object(BudgetService, "_get_active_budget_for_category")
    @patch.object(BudgetService, "_calculate_spent_amount", return_value=500.0)
    def test_refresh_falls_back_to_family_budget(self, _mock_calc, _mock_active):
        """A dependent expense on a dependent-scoped category still refreshes
        the guardian-level (family) budget for that category."""
        family_budget = self._make_doc(**SAMPLE_BUDGET)
        _mock_active.side_effect = [None, family_budget]

        BudgetService.refresh_budget(SAMPLE_USER, "cat-food-dep-001", dependent="dep-son-001")

        self.assertEqual(_mock_active.call_count, 2)
        second_call = _mock_active.call_args_list[1]
        self.assertEqual(second_call.kwargs["dependent"], None)
        args, kwargs = _mock_calc.call_args
        self.assertEqual(kwargs.get("dependent"), None)

    @patch.object(BudgetService, "_get_active_budget_for_category", return_value=None)
    @patch.object(BudgetService, "_calculate_spent_amount")
    def test_refresh_noop_when_no_budget_at_all(self, _mock_calc, _mock_active):
        BudgetService.refresh_budget(SAMPLE_USER, "cat-food-001", dependent="dep-son-001")
        _mock_calc.assert_not_called()


class TestRefreshBudgetFamilySpent(ServiceTestCase):

    def test_family_budget_sums_household_including_dependent_expenses(self):
        with patch.object(frappe.db, "sql", return_value=[(750.0,)]) as mock_sql:
            total = BudgetService._calculate_spent_amount(
                SAMPLE_USER, "cat-food-001", "2026-07-01", "2026-07-31"
            )
            self.assertEqual(total, 750.0)
            sql, params = mock_sql.call_args[0]
            self.assertNotIn("dependent", sql.lower())
            self.assertEqual(params, (SAMPLE_USER, "cat-food-001", "2026-07-01", "2026-07-31"))


class TestBudgetUsageFamilyFallback(ServiceTestCase):

    @patch.object(BudgetService, "_get_active_budget_for_category")
    def test_usage_falls_back_to_family_budget(self, _mock_active):
        family_budget = self._make_doc(
            base=SAMPLE_BUDGET, spent_amount=500.0, allocated_amount=1000.0, alert_threshold_pct=90
        )
        _mock_active.side_effect = [None, family_budget]

        usage = BudgetService.get_budget_usage(
            SAMPLE_USER, "cat-food-dep-001", dependent="dep-son-001"
        )

        self.assertIsNotNone(usage)
        self.assertEqual(usage["spent_amount"], 500.0)
        self.assertEqual(_mock_active.call_count, 2)
        self.assertEqual(_mock_active.call_args_list[1].kwargs["dependent"], None)


class TestListBudgetsWithDependent(ServiceTestCase):

    def test_list_with_dependent_filters(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_BUDGET_DEP]) as mock_get:
            BudgetService.list_budgets(SAMPLE_USER, dependent="dep-son-001")
            filters = mock_get.call_args[1]["filters"]
            self.assertEqual(filters["dependent"], "dep-son-001")

    def test_list_without_dependent_filters_null(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_BUDGET]) as mock_get:
            BudgetService.list_budgets(SAMPLE_USER)
            self.assertEqual(mock_get.call_args[1]["filters"]["dependent"], ["is", "not set"])


class TestListAllActiveBudgets(ServiceTestCase):

    def test_lists_all(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_BUDGET]):
            result = BudgetService.list_all_active_budgets()
            self.assertEqual(len(result), 1)


class TestInlineOverspendSharedCategory(ServiceTestCase):
    """Regression: a dependent expense on a shared (guardian-level) category
    must feed the family budget and must not crash CategoryService with a
    stale dependent argument."""

    @patch.object(BudgetService, "_get_active_budget_for_category")
    @patch("expense_manager.services.budget_service.CategoryService.get_category")
    def test_dependent_expense_on_shared_category_no_crash(self, mock_cat, mock_active):
        family_budget = self._make_doc(
            base=SAMPLE_BUDGET, spent_amount=950.0, allocated_amount=1000.0,
            alert_threshold_pct=90,
        )
        mock_active.side_effect = [None, family_budget]
        mock_cat.return_value.category_name = "Food"

        result = BudgetService.build_inline_overspend_warning(
            SAMPLE_USER, "cat-food-001", dependent="dep-son-001"
        )

        self.assertIn("95", result)
        self.assertEqual(mock_active.call_count, 2)
        self.assertEqual(mock_active.call_args_list[1].kwargs["dependent"], None)
        mock_cat.assert_called_once_with(SAMPLE_USER, "cat-food-001")
