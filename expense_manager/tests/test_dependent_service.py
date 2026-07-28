"""Unit tests for DependentService."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.exceptions import (
    DependentAlreadyExistsError,
    DependentNotFoundError,
    DependentInUseError,
    InvalidRelationshipError,
    InvalidAllowanceError,
)
from expense_manager.tests.base import ServiceTestCase, SAMPLE_USER, SAMPLE_USER_2, SAMPLE_DEPENDENT


class TestCreateDependent(ServiceTestCase):

    @patch.object(DependentService, "dependent_exists", return_value=False)
    def test_create_success(self, _mock_exists):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = DependentService.create_dependent(
                SAMPLE_USER, "Son", "Son", 2000.0
            )
            self.assertEqual(result.dependent_name, "Son")

    @patch.object(DependentService, "dependent_exists", return_value=True)
    def test_create_duplicate_raises(self, _mock_exists):
        with self.assertRaises(DependentAlreadyExistsError):
            DependentService.create_dependent(SAMPLE_USER, "Son", "Son", 2000.0)

    def test_create_invalid_relationship_raises(self):
        with self.assertRaises(InvalidRelationshipError):
            DependentService.create_dependent(SAMPLE_USER, "X", "Invalid", 2000.0)

    def test_create_negative_allowance_raises(self):
        with self.assertRaises(InvalidAllowanceError):
            DependentService.create_dependent(SAMPLE_USER, "X", "Son", -100)

    def test_create_zero_allowance_allowed(self):
        with patch.object(DependentService, "dependent_exists", return_value=False), \
             patch.object(frappe, "get_doc", return_value=self._make_doc()):
            result = DependentService.create_dependent(SAMPLE_USER, "X", "Son", 0)
            self.assertIsNotNone(result)

    def test_create_strips_whitespace(self):
        with patch.object(DependentService, "dependent_exists", return_value=False), \
             patch.object(frappe, "get_doc", return_value=self._make_doc(dependent_name="Daughter")):
            result = DependentService.create_dependent(SAMPLE_USER, "  daughter  ", "Daughter", 1000)
            self.assertEqual(result.dependent_name, "Daughter")


class TestGetDependent(ServiceTestCase):

    def test_get_success(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = DependentService.get_dependent(SAMPLE_USER, "dep-son-001")
            self.assertEqual(result.name, "dep-son-001")

    def test_get_not_found(self):
        with patch.object(frappe, "get_doc", side_effect=frappe.DoesNotExistError):
            with self.assertRaises(DependentNotFoundError):
                DependentService.get_dependent(SAMPLE_USER, "nonexistent")

    def test_get_wrong_guardian(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(DependentNotFoundError):
                DependentService.get_dependent(SAMPLE_USER_2, "dep-son-001")


class TestDependentExists(ServiceTestCase):

    def test_exists_true(self):
        with patch.object(frappe.db, "exists", return_value="dep-son-001"):
            self.assertTrue(DependentService.dependent_exists(SAMPLE_USER, "Son"))

    def test_exists_false(self):
        with patch.object(frappe.db, "exists", return_value=None):
            self.assertFalse(DependentService.dependent_exists(SAMPLE_USER, "Nonexistent"))


class TestUpdateDependent(ServiceTestCase):

    def test_update_name(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "dependent_exists", return_value=False):
            DependentService.update_dependent(SAMPLE_USER, "dep-son-001", dependent_name="Child")
            doc.save.assert_called_once()

    def test_update_duplicate_name_raises(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "dependent_exists", return_value=True):
            with self.assertRaises(DependentAlreadyExistsError):
                DependentService.update_dependent(SAMPLE_USER, "dep-son-001", dependent_name="Daughter")


class TestDeleteDependent(ServiceTestCase):

    def test_delete_success(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value=None):
            DependentService.delete_dependent(SAMPLE_USER, "dep-son-001")
            doc.delete.assert_called_once()

    def test_delete_in_use_raises(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value="some-expense"):
            with self.assertRaises(DependentInUseError):
                DependentService.delete_dependent(SAMPLE_USER, "dep-son-001")


class TestArchiveRestore(ServiceTestCase):

    def test_archive(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        with patch.object(frappe, "get_doc", return_value=doc):
            DependentService.archive_dependent(SAMPLE_USER, "dep-son-001")
            self.assertFalse(doc.is_active)

    def test_restore(self):
        doc = self._make_doc(base=SAMPLE_DEPENDENT, is_active=0)
        with patch.object(frappe, "get_doc", return_value=doc):
            DependentService.restore_dependent(SAMPLE_USER, "dep-son-001")
            self.assertTrue(doc.is_active)

    def test_archive_idempotent(self):
        doc = self._make_doc(base=SAMPLE_DEPENDENT, is_active=0)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = DependentService.archive_dependent(SAMPLE_USER, "dep-son-001")
            doc.save.assert_not_called()


class TestListDependents(ServiceTestCase):

    def test_list_returns_data(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_DEPENDENT]):
            result = DependentService.list_dependents(SAMPLE_USER)
            self.assertEqual(len(result), 1)

    def test_list_active_only(self):
        with patch.object(frappe, "get_all", return_value=[]) as mock_get:
            DependentService.list_dependents(SAMPLE_USER, active_only=True)
            filters = mock_get.call_args[1]["filters"]
            self.assertEqual(filters["is_active"], 1)


class TestSearchDependents(ServiceTestCase):

    def test_search_empty_returns_empty(self):
        result = DependentService.search_dependents(SAMPLE_USER, "")
        self.assertEqual(result, [])

    def test_search_delegates(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_DEPENDENT]) as mock_get:
            result = DependentService.search_dependents(SAMPLE_USER, "Son")
            self.assertEqual(len(result), 1)


class TestGetActiveDependentByTelegramId(ServiceTestCase):

    def test_resolves_telegram_id(self):
        with patch.object(frappe.db, "get_value", side_effect=["dep-son-001", SAMPLE_USER]):
            result = DependentService.get_active_dependent_by_telegram_id("123456")
            self.assertEqual(result["name"], "dep-son-001")
            self.assertEqual(result["guardian"], SAMPLE_USER)

    def test_returns_none_when_not_found(self):
        with patch.object(frappe.db, "get_value", return_value=None):
            result = DependentService.get_active_dependent_by_telegram_id("999999")
            self.assertIsNone(result)
