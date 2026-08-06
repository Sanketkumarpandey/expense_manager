"""Unit tests for the Telegram Link DocType uniqueness validation.

The uniqueness rules on the DocType must only consider *active* links,
so that unlink -> re-link works: unlink deactivates the row instead of
deleting it, and the old inactive row must not block a fresh link.
"""

from unittest import TestCase
from unittest.mock import patch

import frappe

from expense_manager.expense_manager.doctype.telegram_link.telegram_link import (
    TelegramLink,
)
from expense_manager.tests.base import SAMPLE_USER


class TestTelegramLinkUniqueValidation(TestCase):

    def setUp(self) -> None:
        self.doc = TelegramLink(
            {
                "doctype": "Telegram Link",
                "user": SAMPLE_USER,
                "telegram_user_id": "999888777",
                "name": "tl-new-001",
            }
        )

    def test_unique_user_scopes_to_active_links(self) -> None:
        """A prior inactive link (from an unlink) must not block re-linking."""
        with patch.object(frappe.db, "exists", return_value=None) as mock_exists:
            self.doc.validate_unique_user()
            filters = mock_exists.call_args[0][1]
            self.assertEqual(filters["user"], SAMPLE_USER)
            self.assertEqual(filters["is_active"], 1)

    def test_unique_user_throws_when_active_link_exists(self) -> None:
        with patch.object(frappe.db, "exists", return_value="tl-old-001"):
            with patch.object(
                frappe, "throw", side_effect=Exception("frappe.throw")
            ) as mock_throw:
                with self.assertRaises(Exception):
                    self.doc.validate_unique_user()
            mock_throw.assert_called_once()

    def test_unique_telegram_user_scopes_to_active_links(self) -> None:
        """Re-linking the same Telegram account after unlink must not block."""
        with patch.object(frappe.db, "exists", return_value=None) as mock_exists:
            self.doc.validate_unique_telegram_user()
            filters = mock_exists.call_args[0][1]
            self.assertEqual(filters["telegram_user_id"], "999888777")
            self.assertEqual(filters["is_active"], 1)

    def test_unique_telegram_user_throws_when_active_link_exists(self) -> None:
        with patch.object(frappe.db, "exists", return_value="tl-other-user"):
            with patch.object(
                frappe, "throw", side_effect=Exception("frappe.throw")
            ) as mock_throw:
                with self.assertRaises(Exception):
                    self.doc.validate_unique_telegram_user()
            mock_throw.assert_called_once()
