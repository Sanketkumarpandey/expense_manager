"""Unit tests for Dependent.telegram_user_id uniqueness (F-5).

A Telegram account must map to at most one identity in the system. The
Dependent DocType must therefore reject a telegram_user_id that is
already used by another Dependent OR by an active Telegram Link, so
identity resolution (get_active_dependent_by_telegram_id vs
get_user_by_telegram) can never be ambiguous.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from expense_manager.expense_manager.doctype.dependent.dependent import (
	Dependent,
)
from expense_manager.tests.base import SAMPLE_USER

TELEGRAM_ID = "999888777"


def _make_dependent():
	return Dependent(
		{
			"doctype": "Dependent",
			"dependent_name": "Son",
			"guardian": SAMPLE_USER,
			"relationship": "Son",
			"default_monthly_allowance": 2000.0,
			"telegram_user_id": TELEGRAM_ID,
			"name": "dep-new-001",
		}
	)


class TestDependentTelegramIdUniqueness(TestCase):
	def test_allows_when_id_unused(self):
		doc = _make_dependent()
		with patch.object(frappe.db, "exists", return_value=None) as mock_exists:
			doc.validate_telegram_user_id()
		self.assertEqual(mock_exists.call_count, 2)

	def test_rejects_digit_invalid_id(self):
		doc = _make_dependent()
		doc.telegram_user_id = "not-digits"
		with patch.object(frappe, "throw", side_effect=Exception("frappe.throw")) as mock_throw:
			with self.assertRaises(Exception):
				doc.validate_telegram_user_id()
		mock_throw.assert_called_once()

	def test_rejects_when_another_dependent_uses_id(self):
		doc = _make_dependent()

		def exists_side_effect(doctype, filters):
			if doctype == "Dependent":
				return "dep-existing-001"
			return None

		with patch.object(frappe.db, "exists", side_effect=exists_side_effect) as mock_exists:
			with patch.object(frappe, "throw", side_effect=Exception("frappe.throw")) as mock_throw:
				with self.assertRaises(Exception):
					doc.validate_telegram_user_id()
		mock_throw.assert_called_once()
		dependent_filters = mock_exists.call_args_list[0][0][1]
		self.assertEqual(dependent_filters["telegram_user_id"], TELEGRAM_ID)
		self.assertEqual(dependent_filters["name"], ["!=", "dep-new-001"])

	def test_rejects_when_active_telegram_link_uses_id(self):
		doc = _make_dependent()

		def exists_side_effect(doctype, filters):
			if doctype == "Telegram Link":
				return "tl-existing-001"
			return None

		with patch.object(frappe.db, "exists", side_effect=exists_side_effect):
			with patch.object(frappe, "throw", side_effect=Exception("frappe.throw")) as mock_throw:
				with self.assertRaises(Exception):
					doc.validate_telegram_user_id()
		mock_throw.assert_called_once()
