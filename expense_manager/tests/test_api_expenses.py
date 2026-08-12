"""Unit tests for whitelisted Expense API endpoints (thin wrappers).

These tests exercise the API layer only: argument passthrough, error
mapping, and response enrichment. Business logic is covered by the
service tests (test_ai_service, test_expense_service).
"""

from unittest import TestCase
from unittest.mock import MagicMock, patch

from expense_manager.ai.exceptions import IncomeDetectedError
from expense_manager.api import expenses as api_expenses
from expense_manager.config.exceptions import ConfigurationError
from expense_manager.constants.expense import ExpenseSource


class TestApiCreateExpenseFromText(TestCase):
	"""Desk/REST quick-add endpoint built on AIService."""

	def setUp(self) -> None:
		self.patches = [
			patch.object(api_expenses.frappe, "logger", return_value=MagicMock()),
		]
		for p in self.patches:
			p.start()

	def tearDown(self) -> None:
		for p in reversed(self.patches):
			p.stop()

	def _expense_doc(self, **overrides):
		doc = MagicMock()
		data = {
			"name": "exp-ai-001",
			"category": "cat-food-001",
			"amount": 200.0,
			"expense_date": "2026-08-04",
			"dependent": None,
			"description": "Lunch 250",
			"source": ExpenseSource.WEB,
			"payment_method": None,
		}
		data.update(overrides)
		for key, value in data.items():
			setattr(doc, key, value)
		doc.as_dict.return_value = data
		return doc

	def test_success_passes_web_source_and_enriches_response(self):
		doc = self._expense_doc()
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(
				api_expenses,
				"_category_lookup",
				return_value={
					"cat-food-001": {"category_name": "Food", "icon": "🍽️"},
				},
			),
			patch.object(api_expenses, "BudgetService") as mock_budget,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.return_value = doc
			mock_budget.build_inline_overspend_warning.return_value = ""

			result = api_expenses.create_expense_from_text("lunch 250")

			self.assertEqual(result["name"], "exp-ai-001")
			self.assertEqual(result["category_name"], "Food")
			self.assertEqual(result["category_icon"], "🍽️")
			self.assertNotIn("warning", result)
			mock_ai.create_expense_from_text.assert_called_once_with(
				owner_user="guardian@example.com",
				text="lunch 250",
				dependent=None,
				source=ExpenseSource.WEB,
			)
			mock_budget.build_inline_overspend_warning.assert_called_once_with(
				"guardian@example.com", "cat-food-001", dependent=None
			)

	def test_dependent_is_forwarded(self):
		doc = self._expense_doc(dependent="dep-son-001")
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_category_lookup", return_value={}),
			patch.object(api_expenses, "BudgetService", build_inline_overspend_warning=lambda *a, **k: ""),
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.return_value = doc

			result = api_expenses.create_expense_from_text("lunch 250", dependent="dep-son-001")

			mock_ai.create_expense_from_text.assert_called_once_with(
				owner_user="guardian@example.com",
				text="lunch 250",
				dependent="dep-son-001",
				source=ExpenseSource.WEB,
			)
			self.assertEqual(result["dependent"], "dep-son-001")

	def test_overspend_warning_is_appended(self):
		doc = self._expense_doc()
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_category_lookup", return_value={}),
			patch.object(api_expenses, "BudgetService") as mock_budget,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.return_value = doc
			mock_budget.build_inline_overspend_warning.return_value = "⚠️ Budget exceeded!"

			result = api_expenses.create_expense_from_text("lunch 250")

			self.assertEqual(result["warning"], "⚠️ Budget exceeded!")

	def test_overspend_payload_is_appended(self):
		doc = self._expense_doc()
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_category_lookup", return_value={}),
			patch.object(api_expenses, "BudgetService") as mock_budget,
			patch.object(api_expenses, "CategoryService") as mock_cat,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.return_value = doc
			mock_budget.build_inline_overspend_warning.return_value = ""
			mock_budget.get_budget_usage.return_value = {
				"allocated_amount": 1000.0,
				"spent_amount": 1200.0,
				"remaining_amount": -200.0,
				"pct_used": 120.0,
				"is_overspent": True,
				"alert_threshold_pct": 90,
			}
			category = MagicMock()
			category.category_name = "Food"
			mock_cat.get_category.return_value = category

			result = api_expenses.create_expense_from_text("lunch 250")

			self.assertNotIn("warning", result)
			self.assertEqual(result["overspend"]["category"], "cat-food-001")
			self.assertEqual(result["overspend"]["category_name"], "Food")
			self.assertEqual(result["overspend"]["spent_amount"], 1200.0)
			self.assertEqual(result["overspend"]["allocated_amount"], 1000.0)

	def test_no_overspend_payload_when_budget_ok(self):
		doc = self._expense_doc()
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_category_lookup", return_value={}),
			patch.object(api_expenses, "BudgetService") as mock_budget,
			patch.object(api_expenses, "CategoryService") as mock_cat,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.return_value = doc
			mock_budget.build_inline_overspend_warning.return_value = ""
			mock_budget.get_budget_usage.return_value = {
				"allocated_amount": 1000.0,
				"spent_amount": 400.0,
				"remaining_amount": 600.0,
				"pct_used": 40.0,
				"is_overspent": False,
				"alert_threshold_pct": 90,
			}

			result = api_expenses.create_expense_from_text("lunch 250")

			self.assertNotIn("overspend", result)
			mock_cat.get_category.assert_not_called()

	def test_config_error_returns_friendly_message(self):
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.side_effect = ConfigurationError("missing groq key")

			result = api_expenses.create_expense_from_text("lunch 250")

			self.assertFalse(result["success"])
			self.assertIn("isn't set up yet", result["message"])

	def test_ai_error_message_is_surfaced(self):
		with (
			patch.object(api_expenses, "AIService") as mock_ai,
			patch.object(api_expenses, "_current_user", return_value="guardian@example.com"),
		):
			mock_ai.create_expense_from_text.side_effect = IncomeDetectedError(
				"Looks like income, not an expense."
			)

			result = api_expenses.create_expense_from_text("salary credited")

			self.assertFalse(result["success"])
			self.assertEqual(result["message"], "Looks like income, not an expense.")
