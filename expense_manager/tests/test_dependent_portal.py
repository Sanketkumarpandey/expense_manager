"""Unit tests for the Dependent Portal backend and access tokens."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from expense_manager.api.dependents import get_portal_data
from expense_manager.expense_manager.doctype.dependent.dependent import Dependent
from expense_manager.tests.base import SAMPLE_USER


class TestDependentPortal(TestCase):
	def test_auto_generates_access_token_on_insert(self):
		doc = Dependent(
			{
				"doctype": "Dependent",
				"dependent_name": "Portal Test Kid",
				"guardian": SAMPLE_USER,
				"relationship": "Child",
				"default_monthly_allowance": 1000.0,
				"telegram_user_id": "11223344",
			}
		)
		self.assertIsNone(doc.access_token)
		doc.before_insert()
		self.assertIsNotNone(doc.access_token)
		self.assertTrue(len(doc.access_token) >= 20)

	def test_get_portal_data_requires_token(self):
		res = get_portal_data(token=None)
		self.assertFalse(res.get("success"))
		self.assertIn("Access token is required", res.get("message", ""))

	def test_get_portal_data_returns_error_for_invalid_token(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			res = get_portal_data(token="non-existent-token-999")
			self.assertFalse(res.get("success"))
			self.assertIn("not found", res.get("message", ""))

	def test_get_portal_data_success_structure(self):
		mock_dep = {
			"name": "dep-portal-1",
			"dependent_name": "Alice Kid",
			"guardian": SAMPLE_USER,
			"relationship": "Daughter",
			"default_monthly_allowance": 1500.0,
			"total_savings": 500.0,
			"allow_carry_forward": 1,
			"is_active": 1,
			"access_token": "valid-token-abc-123",
		}
		orig_get_value = frappe.db.get_value

		def mock_get_val(doctype, filters=None, *args, **kwargs):
			if doctype == "Dependent":
				return mock_dep
			return orig_get_value(doctype, filters, *args, **kwargs)

		with patch.object(frappe.db, "get_value", side_effect=mock_get_val):
			with patch(
				"expense_manager.services.pocket_money_service.PocketMoneyService.get_balance",
				return_value={
					"allocation": "alloc-1",
					"allocated_amount": 1500.0,
					"spent_amount": 300.0,
					"carry_forward": 0.0,
					"remaining_amount": 1200.0,
					"available_amount": 1200.0,
					"total_savings": 500.0,
				},
			):
				with patch(
					"expense_manager.services.dependent_service.DependentService.list_allowed_categories",
					return_value=[{"name": "cat-food", "category_name": "Food", "icon": "🍽️"}],
				):
					with patch(
						"expense_manager.services.budget_service.BudgetService.list_budgets", return_value=[]
					):
						with patch.object(frappe, "get_all", return_value=[]):
							with patch(
								"expense_manager.services.report_service.ReportService.get_spending_trend",
								return_value=[],
							):
								res = get_portal_data(token="valid-token-abc-123")
								self.assertTrue(res.get("success"))
								self.assertEqual(res["dependent"]["dependent_name"], "Alice Kid")
								self.assertEqual(res["balance"]["remaining_amount"], 1200.0)
								self.assertEqual(len(res["category_breakdown"]), 1)
								self.assertEqual(res["category_breakdown"][0]["category_name"], "Food")
