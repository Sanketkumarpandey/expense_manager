"""Unit tests for CategoryService."""

from unittest import TestCase
from unittest.mock import MagicMock, patch, PropertyMock

import frappe
from expense_manager.services.category_service import CategoryService
from expense_manager.services.exceptions import (
    CategoryAlreadyExistsError,
    CategoryNotFoundError,
    CategoryInUseError,
)
from expense_manager.tests.base import ServiceTestCase, SAMPLE_USER, SAMPLE_USER_2, SAMPLE_CATEGORY
from expense_manager.expense_manager.doctype.user.hooks import user_on_update


class TestCreateCategory(ServiceTestCase):

    @patch.object(CategoryService, "category_exists", return_value=False)
    def test_create_category_success(self, _mock_exists):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = CategoryService.create_category(SAMPLE_USER, "Food", "🍽️")
            self.assertEqual(result.category_name, "Food")

    @patch.object(CategoryService, "category_exists", return_value=True)
    def test_create_duplicate_raises(self, _mock_exists):
        with self.assertRaises(CategoryAlreadyExistsError):
            CategoryService.create_category(SAMPLE_USER, "Food")

    @patch.object(CategoryService, "category_exists", return_value=False)
    def test_create_strips_whitespace(self, _mock_exists):
        doc = self._make_doc(category_name="Transport")
        with patch.object(frappe, "get_doc", return_value=doc):
            result = CategoryService.create_category(SAMPLE_USER, "  Transport  ")
            self.assertEqual(result.category_name, "Transport")


class TestGetCategory(ServiceTestCase):

    def test_get_category_success(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = CategoryService.get_category(SAMPLE_USER, "cat-food-001")
            self.assertEqual(result.name, "cat-food-001")

    def test_get_category_not_found(self):
        with patch.object(frappe, "get_doc", side_effect=frappe.DoesNotExistError):
            with self.assertRaises(CategoryNotFoundError):
                CategoryService.get_category(SAMPLE_USER, "nonexistent")

    def test_get_category_wrong_owner(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc):
            with self.assertRaises(CategoryNotFoundError):
                CategoryService.get_category(SAMPLE_USER_2, "cat-food-001")


class TestCategoryExists(ServiceTestCase):

    def test_exists_returns_true(self):
        with patch.object(frappe.db, "exists", return_value="cat-food-001"):
            self.assertTrue(CategoryService.category_exists(SAMPLE_USER, "Food"))

    def test_exists_returns_false(self):
        with patch.object(frappe.db, "exists", return_value=None):
            self.assertFalse(CategoryService.category_exists(SAMPLE_USER, "Nonexistent"))


class TestUpdateCategory(ServiceTestCase):

    def test_update_name(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(CategoryService, "category_exists", return_value=False):
            result = CategoryService.update_category(SAMPLE_USER, "cat-food-001", category_name="Lunch")
            doc.save.assert_called_once()

    def test_update_duplicate_name_raises(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(CategoryService, "category_exists", return_value=True):
            with self.assertRaises(CategoryAlreadyExistsError):
                CategoryService.update_category(SAMPLE_USER, "cat-food-001", category_name="Transport")


class TestDeleteCategory(ServiceTestCase):

    def test_delete_success(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value=None):
            CategoryService.delete_category(SAMPLE_USER, "cat-food-001")
            doc.delete.assert_called_once()

    def test_delete_in_use_raises(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value="some-expense"):
            with self.assertRaises(CategoryInUseError):
                CategoryService.delete_category(SAMPLE_USER, "cat-food-001")


class TestArchiveRestore(ServiceTestCase):

    def test_archive_sets_inactive(self):
        doc = self._make_doc(**SAMPLE_CATEGORY)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = CategoryService.archive_category(SAMPLE_USER, "cat-food-001")
            self.assertFalse(doc.is_active)

    def test_restore_sets_active(self):
        doc = self._make_doc(base=SAMPLE_CATEGORY, is_active=0)
        with patch.object(frappe, "get_doc", return_value=doc):
            result = CategoryService.restore_category(SAMPLE_USER, "cat-food-001")
            self.assertTrue(doc.is_active)


class TestListCategories(ServiceTestCase):

    def test_list_returns_data(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_CATEGORY]):
            result = CategoryService.list_categories(SAMPLE_USER)
            self.assertEqual(len(result), 1)

    def test_list_active_only_filter(self):
        with patch.object(frappe, "get_all", return_value=[]) as mock_get:
            CategoryService.list_categories(SAMPLE_USER, active_only=True)
            filters = mock_get.call_args[1]["filters"]
            self.assertEqual(filters["is_active"], 1)


class TestSearchCategories(ServiceTestCase):

    def test_search_empty_text_returns_empty(self):
        result = CategoryService.search_categories(SAMPLE_USER, "")
        self.assertEqual(result, [])

    def test_search_delegates_to_get_all(self):
        with patch.object(frappe, "get_all", return_value=[SAMPLE_CATEGORY]) as mock_get:
            result = CategoryService.search_categories(SAMPLE_USER, "Food")
            self.assertEqual(len(result), 1)


class TestCreateDefaultCategories(ServiceTestCase):

    def test_creates_defaults(self):
        with patch.object(frappe, "get_doc", return_value=self._make_doc()), \
             patch.object(frappe.db, "exists", return_value=None):
            result = CategoryService.create_default_categories(SAMPLE_USER)
            self.assertEqual(len(result), 13)

    def test_skips_existing(self):
        with patch.object(frappe.db, "exists", return_value="existing"):
            result = CategoryService.create_default_categories(SAMPLE_USER)
            self.assertEqual(len(result), 0)


class TestUserOnUpdateHook(ServiceTestCase):

    def test_seeds_categories_for_expense_manager_user(self):
        doc = MagicMock()
        doc.name = SAMPLE_USER
        with patch("frappe.get_roles", return_value=["Expense Manager User"]), \
             patch.object(frappe.db, "exists", return_value=None), \
             patch.object(frappe, "get_doc", return_value=self._make_doc()):
            user_on_update(doc)
            # No exception — categories were seeded.

    def test_skips_non_expense_manager_user(self):
        doc = MagicMock()
        doc.name = SAMPLE_USER
        with patch("frappe.get_roles", return_value=["System Manager"]), \
             patch("expense_manager.services.category_service.CategoryService.create_default_categories") as mock_create:
            user_on_update(doc)
            mock_create.assert_not_called()

    def test_skips_when_already_seeded(self):
        doc = MagicMock()
        doc.name = SAMPLE_USER
        with patch("frappe.get_roles", return_value=["Expense Manager User"]), \
             patch.object(frappe.db, "exists", return_value="existing"):
            user_on_update(doc)
            # Idempotent: no categories created (exists returns existing),
            # but no exception raised.
