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
    CategoryNotFoundError,
)
from expense_manager.tests.base import ServiceTestCase, SAMPLE_USER, SAMPLE_USER_2, SAMPLE_DEPENDENT, SAMPLE_CATEGORY


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

    def test_list_includes_total_savings_field(self):
        with patch.object(frappe, "get_all", return_value=[]) as mock_get:
            DependentService.list_dependents(SAMPLE_USER)
            fields = mock_get.call_args[1]["fields"]
            self.assertIn("total_savings", fields)

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


class TestListAllowedCategories(ServiceTestCase):
    """DependentService.list_allowed_categories is the single source of truth
    for the shared category pool: an empty child table means ALL guardian
    active categories are allowed."""

    GYM = {
        "name": "cat-gym-001",
        "category_name": "Gym",
        "icon": "🏋️",
        "owner_user": SAMPLE_USER,
        "is_active": 1,
    }

    def _make_dep_doc(self, allowed_categories=None):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = allowed_categories or []
        doc.get = lambda key, default=None: getattr(doc, key, default)
        return doc

    def test_empty_table_falls_back_to_all_categories(self):
        doc = self._make_dep_doc([])
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ) as mock_list:
            result = DependentService.list_allowed_categories(SAMPLE_USER, "dep-son-001")

        self.assertEqual(result, [SAMPLE_CATEGORY])
        mock_list.assert_called_once_with(SAMPLE_USER, active_only=True)

    def test_restricted_list_only_returns_allowed(self):
        doc = self._make_dep_doc([{"category": "cat-food-001", "is_active": 1}])
        all_cats = [SAMPLE_CATEGORY, self.GYM]
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=all_cats,
             ):
            result = DependentService.list_allowed_categories(SAMPLE_USER, "dep-son-001")

        self.assertEqual([row["name"] for row in result], ["cat-food-001"])

    def test_inactive_allowed_row_falls_back_to_all(self):
        doc = self._make_dep_doc([{"category": "cat-food-001", "is_active": 0}])
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ):
            result = DependentService.list_allowed_categories(SAMPLE_USER, "dep-son-001")

        self.assertEqual(result, [SAMPLE_CATEGORY])

    def test_active_only_parameter_passed_through(self):
        doc = self._make_dep_doc([{"category": "cat-food-001", "is_active": 1}])
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ) as mock_list:
            DependentService.list_allowed_categories(SAMPLE_USER, "dep-son-001", active_only=False)

        mock_list.assert_called_once_with(SAMPLE_USER, active_only=False)

    def test_skips_allowed_rows_for_missing_categories(self):
        doc = self._make_dep_doc([
            {"category": "cat-gone-001", "is_active": 1},
            {"category": "cat-food-001", "is_active": 1},
        ])
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ):
            result = DependentService.list_allowed_categories(SAMPLE_USER, "dep-son-001")

        self.assertEqual([row["name"] for row in result], ["cat-food-001"])


class TestAddAllowedCategory(ServiceTestCase):

    def test_add_by_doc_name(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = []
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "_resolve_category_id", return_value="cat-food-001"):
            result = DependentService.add_allowed_category(SAMPLE_USER, "dep-son-001", "cat-food-001")

        doc.append.assert_called_once_with(
            "allowed_categories", {"category": "cat-food-001", "is_active": 1}
        )
        doc.save.assert_called_once()
        self.assertEqual(result, doc)

    def test_add_is_idempotent(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = [{"category": "cat-food-001", "is_active": 1}]
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "_resolve_category_id", return_value="cat-food-001"):
            DependentService.add_allowed_category(SAMPLE_USER, "dep-son-001", "cat-food-001")

        doc.append.assert_not_called()
        doc.save.assert_not_called()

    def test_add_unknown_category_raises(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = []
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(
                DependentService, "_resolve_category_id",
                side_effect=CategoryNotFoundError("Category not found."),
             ):
            with self.assertRaises(CategoryNotFoundError):
                DependentService.add_allowed_category(SAMPLE_USER, "dep-son-001", "nope")

        doc.save.assert_not_called()


class TestRemoveAllowedCategory(ServiceTestCase):

    def test_remove_existing(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        row = {"category": "cat-food-001", "is_active": 1}
        doc.allowed_categories = [row]
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "_resolve_category_id", return_value="cat-food-001"):
            result = DependentService.remove_allowed_category(SAMPLE_USER, "dep-son-001", "cat-food-001")

        doc.remove.assert_called_once_with(row)
        doc.save.assert_called_once()
        self.assertEqual(result, doc)

    def test_remove_absent_is_noop(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = [{"category": "cat-gym-001", "is_active": 1}]
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(DependentService, "_resolve_category_id", return_value="cat-food-001"):
            DependentService.remove_allowed_category(SAMPLE_USER, "dep-son-001", "cat-food-001")

        doc.remove.assert_not_called()
        doc.save.assert_called_once()

    def test_remove_unknown_category_raises(self):
        doc = self._make_doc(**SAMPLE_DEPENDENT)
        doc.allowed_categories = []
        doc.get = lambda key, default=None: getattr(doc, key, default)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(
                DependentService, "_resolve_category_id",
                side_effect=CategoryNotFoundError("Category not found."),
             ):
            with self.assertRaises(CategoryNotFoundError):
                DependentService.remove_allowed_category(SAMPLE_USER, "dep-son-001", "nope")

        doc.save.assert_not_called()


class TestResolveCategoryId(ServiceTestCase):

    def test_resolves_by_doc_name(self):
        with patch.object(frappe.db, "exists", return_value="cat-food-001"), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.get_category",
                return_value=self._make_doc(**SAMPLE_CATEGORY),
             ):
            result = DependentService._resolve_category_id(SAMPLE_USER, "cat-food-001")

        self.assertEqual(result, "cat-food-001")

    def test_resolves_by_category_name_case_insensitive(self):
        with patch.object(frappe.db, "exists", return_value=None), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ):
            result = DependentService._resolve_category_id(SAMPLE_USER, "food")

        self.assertEqual(result, "cat-food-001")

    def test_unknown_category_raises(self):
        with patch.object(frappe.db, "exists", return_value=None), \
             patch(
                "expense_manager.services.dependent_service.CategoryService.list_categories",
                return_value=[SAMPLE_CATEGORY],
             ):
            with self.assertRaises(CategoryNotFoundError):
                DependentService._resolve_category_id(SAMPLE_USER, "zzz")
