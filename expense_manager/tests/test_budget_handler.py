"""Unit tests for the /budgets and /balance Telegram handlers (icons)."""

from unittest import TestCase
from unittest.mock import patch

from expense_manager.telegram.handlers.budget import handle_budgets, handle_balance
from expense_manager.telegram.services.telegram_service import TelegramService


UPDATE = {"message": {"from": {"id": 1343702125}, "chat": {"id": 1343702125}}}


class TestHandleBudgets(TestCase):

    def _budget_row(self, **overrides):
        row = {
            "category": "cat-food-001",
            "category_name": "Food",
            "category_icon": "🍽️",
            "spent_amount": 1200.0,
            "allocated_amount": 5000.0,
            "remaining_amount": 3800.0,
            "percentage": 24.0,
            "is_overspent": False,
        }
        row.update(overrides)
        return row

    def test_renders_icon_next_to_category_name(self):
        with patch.object(TelegramService, "get_budget", return_value={
            "success": True,
            "data": [self._budget_row()],
        }):
            text = handle_budgets(UPDATE)
        self.assertIn("🍽️ Food", text)
        self.assertIn("1200.0 / 5000.0", text)
        self.assertIn("24.0%", text)

    def test_no_icon_omits_prefix(self):
        with patch.object(TelegramService, "get_budget", return_value={
            "success": True,
            "data": [self._budget_row(category_icon="")],
        }):
            text = handle_budgets(UPDATE)
        self.assertNotIn("️ ", text)
        self.assertIn("- Food:", text)

    def test_overspent_label_rendered(self):
        with patch.object(TelegramService, "get_budget", return_value={
            "success": True,
            "data": [self._budget_row(is_overspent=True)],
        }):
            text = handle_budgets(UPDATE)
        self.assertIn("— over budget", text)


class TestHandleBalance(TestCase):

    def _budget_row(self, **overrides):
        row = {
            "category": "cat-med-001",
            "category_name": "Medical",
            "category_icon": "🏥",
            "spent_amount": 500.0,
            "allocated_amount": 2000.0,
            "remaining_amount": 1500.0,
            "percentage": 25.0,
            "is_overspent": False,
        }
        row.update(overrides)
        return row

    def _linked_status(self, is_dependent=False):
        return {"success": True, "data": {"linked": True, "is_dependent": is_dependent}}

    def test_guardian_balance_renders_icon(self):
        with patch.object(TelegramService, "get_link_status",
                          return_value=self._linked_status()), \
             patch.object(TelegramService, "get_budget", return_value={
                 "success": True,
                 "data": [self._budget_row()],
             }):
            text = handle_balance(UPDATE)
        self.assertIn("🏥 Medical", text)
        self.assertIn("remaining 1500.0", text)

    def test_guardian_balance_no_icon_omits_prefix(self):
        with patch.object(TelegramService, "get_link_status",
                          return_value=self._linked_status()), \
             patch.object(TelegramService, "get_budget", return_value={
                 "success": True,
                 "data": [self._budget_row(category_icon="")],
             }):
            text = handle_balance(UPDATE)
        self.assertIn("- Medical: remaining 1500.0", text)

    def test_dependent_balance_shows_savings(self):
        with patch.object(TelegramService, "get_link_status",
                          return_value=self._linked_status(is_dependent=True)), \
             patch.object(TelegramService, "get_pocket_money", return_value={
                 "success": True,
                 "data": [{"remaining_amount": 1200, "total_savings": 4000}],
             }):
            text = handle_balance(UPDATE)
        self.assertIn("Spendable: ₹1200 | Savings: ₹4000", text)

    def test_unlinked_returns_prompt(self):
        with patch.object(TelegramService, "get_link_status",
                          return_value={"success": True, "data": {"linked": False}}):
            text = handle_balance(UPDATE)
        self.assertIn("/link", text)
