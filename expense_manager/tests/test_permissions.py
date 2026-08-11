"""Tests for scripted Expense row-level permissions (F-2).

Covers the has_permission hook (document-level access), the
permission_query_conditions hook (list scoping), and the controller's
before_insert owner binding.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from expense_manager.expense_manager.doctype.expense.expense import Expense
from expense_manager.permissions import (
    expense_has_permission,
    expense_permission_query_conditions,
)
from expense_manager.tests.base import SAMPLE_USER, SAMPLE_USER_2


def _doc(owner_user=None):
    doc = MagicMock()
    doc.owner_user = owner_user
    return doc


class TestExpenseHasPermission(TestCase):

    def test_system_manager_can_access_any_doc(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["System Manager"]):
            self.assertTrue(expense_has_permission(doc, "read", user="admin@example.com"))

    def test_administrator_can_access_any_doc(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        self.assertTrue(expense_has_permission(doc, "read", user="Administrator"))

    def test_owner_can_read_own_doc(self):
        doc = _doc(owner_user=SAMPLE_USER)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertTrue(expense_has_permission(doc, "read", user=SAMPLE_USER))

    def test_non_owner_cannot_read(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertFalse(expense_has_permission(doc, "read", user=SAMPLE_USER))

    def test_non_owner_cannot_write(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertFalse(expense_has_permission(doc, "write", user=SAMPLE_USER))

    def test_non_owner_cannot_delete(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertFalse(expense_has_permission(doc, "delete", user=SAMPLE_USER))

    def test_create_allowed_when_owner_unset(self):
        doc = _doc(owner_user=None)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertTrue(expense_has_permission(doc, "create", user=SAMPLE_USER))

    def test_create_allowed_when_owner_matches(self):
        doc = _doc(owner_user=SAMPLE_USER)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertTrue(expense_has_permission(doc, "create", user=SAMPLE_USER))

    def test_create_spoofed_owner_denied(self):
        doc = _doc(owner_user=SAMPLE_USER_2)
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertFalse(expense_has_permission(doc, "create", user=SAMPLE_USER))

    def test_uses_session_user_when_user_not_passed(self):
        doc = _doc(owner_user=SAMPLE_USER)
        with patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)), \
             patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]):
            self.assertTrue(expense_has_permission(doc, "read"))


class TestExpensePermissionQueryConditions(TestCase):

    def test_system_manager_unrestricted(self):
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["System Manager"]):
            self.assertIsNone(expense_permission_query_conditions(user="admin@example.com"))

    def test_administrator_unrestricted(self):
        self.assertIsNone(expense_permission_query_conditions(user="Administrator"))

    def test_regular_user_scoped(self):
        with patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]), \
             patch("expense_manager.permissions.frappe.db.escape", return_value="'guardian@example.com'"):
            condition = expense_permission_query_conditions(user=SAMPLE_USER)
        self.assertIn("owner_user", condition)
        self.assertIn(SAMPLE_USER, condition)

    def test_uses_session_user_when_user_not_passed(self):
        with patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)), \
             patch("expense_manager.permissions.frappe.get_roles", return_value=["Expense Manager User"]), \
             patch("expense_manager.permissions.frappe.db.escape", return_value="'guardian@example.com'"):
            condition = expense_permission_query_conditions()
        self.assertIn(SAMPLE_USER, condition)


class TestExpenseBeforeInsertOwnerBinding(TestCase):

    def _make_expense(self, owner_user):
        return Expense({"doctype": "Expense", "owner_user": owner_user})

    def test_forces_session_user_for_regular_user(self):
        expense = self._make_expense(owner_user=SAMPLE_USER_2)
        with patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)), \
             patch("expense_manager.expense_manager.doctype.expense.expense.frappe.get_roles", return_value=["Expense Manager User"]):
            expense.before_insert()
        self.assertEqual(expense.owner_user, SAMPLE_USER)

    def test_binds_session_user_when_owner_unset(self):
        expense = self._make_expense(owner_user=None)
        with patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)), \
             patch("expense_manager.expense_manager.doctype.expense.expense.frappe.get_roles", return_value=["Expense Manager User"]):
            expense.before_insert()
        self.assertEqual(expense.owner_user, SAMPLE_USER)

    def test_guest_session_preserves_server_set_owner(self):
        expense = self._make_expense(owner_user=SAMPLE_USER)
        with patch.object(frappe, "session", SimpleNamespace(user="Guest")), \
             patch("expense_manager.expense_manager.doctype.expense.expense.frappe.get_roles", return_value=["Guest"]):
            expense.before_insert()
        self.assertEqual(expense.owner_user, SAMPLE_USER)

    def test_system_manager_keeps_chosen_owner(self):
        expense = self._make_expense(owner_user=SAMPLE_USER_2)
        with patch.object(frappe, "session", SimpleNamespace(user="admin@example.com")), \
             patch("expense_manager.expense_manager.doctype.expense.expense.frappe.get_roles", return_value=["System Manager"]):
            expense.before_insert()
        self.assertEqual(expense.owner_user, SAMPLE_USER_2)

    def test_administrator_session_binds_when_owner_unset(self):
        expense = self._make_expense(owner_user=None)
        with patch.object(frappe, "session", SimpleNamespace(user="Administrator")), \
             patch("expense_manager.expense_manager.doctype.expense.expense.frappe.get_roles", return_value=["Administrator"]):
            expense.before_insert()
        self.assertEqual(expense.owner_user, "Administrator")
