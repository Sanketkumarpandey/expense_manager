"""Unit tests for PocketMoneyService."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.exceptions import (
    PocketMoneyAllocationNotFoundError,
    PocketMoneyAllocationAlreadyExistsError,
    InvalidAllocationAmountError,
    InvalidAllocationPeriodError,
    InvalidCarryForwardAmountError,
)
from expense_manager.tests.base import ServiceTestCase, SAMPLE_USER, SAMPLE_USER_2, SAMPLE_ALLOCATION, SAMPLE_DEPENDENT


class TestCreateAllocation(ServiceTestCase):

    @patch("expense_manager.services.pocket_money_service.DependentService.get_dependent")
    def test_create_success(self, _mock_dep):
        _mock_dep.return_value = MagicMock()
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value=None):
            result = PocketMoneyService.create_allocation(
                SAMPLE_USER, "dep-son-001", 2000, "Monthly"
            )
            self.assertEqual(result.allocated_amount, 2000)

    def test_create_zero_amount_raises(self):
        with self.assertRaises(InvalidAllocationAmountError):
            PocketMoneyService.create_allocation(SAMPLE_USER, "dep-son-001", 0, "Monthly")

    def test_create_invalid_period_raises(self):
        with self.assertRaises(InvalidAllocationPeriodError):
            PocketMoneyService.create_allocation(SAMPLE_USER, "dep-son-001", 2000, "Daily")

    def test_create_negative_carry_forward_raises(self):
        with self.assertRaises(InvalidCarryForwardAmountError):
            PocketMoneyService.create_allocation(
                SAMPLE_USER, "dep-son-001", 2000, "Monthly", carry_forward_amount=-100
            )

    def test_create_duplicate_active_raises(self):
        with patch.object(frappe.db, "get_value", return_value="existing"):
            with self.assertRaises(PocketMoneyAllocationAlreadyExistsError):
                PocketMoneyService.create_allocation(SAMPLE_USER, "dep-son-001", 2000, "Monthly")


class TestGetAllocation(ServiceTestCase):

    def test_get_success(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent"):
            result = PocketMoneyService.get_allocation(SAMPLE_USER, "pm-001")
            self.assertEqual(result.name, "pm-001")

    def test_get_not_found(self):
        with patch.object(frappe, "get_doc", side_effect=frappe.DoesNotExistError):
            with self.assertRaises(PocketMoneyAllocationNotFoundError):
                PocketMoneyService.get_allocation(SAMPLE_USER, "nonexistent")


class TestUpdateAllocation(ServiceTestCase):

    def test_update_amount(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(frappe, "get_doc", return_value=doc):
            PocketMoneyService.update_allocation(SAMPLE_USER, "pm-001", allocated_amount=3000)
            self.assertEqual(doc.allocated_amount, 3000)
            doc.save.assert_called_once()


class TestDeleteAllocation(ServiceTestCase):

    def test_delete_success(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(frappe, "get_doc", return_value=doc):
            PocketMoneyService.delete_allocation(SAMPLE_USER, "pm-001")
            doc.delete.assert_called_once()


class TestArchiveRestore(ServiceTestCase):

    def test_archive(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(frappe, "get_doc", return_value=doc):
            PocketMoneyService.archive_allocation(SAMPLE_USER, "pm-001")
            self.assertFalse(doc.is_active)

    def test_restore(self):
        doc = self._make_doc(base=SAMPLE_ALLOCATION, is_active=0)
        with patch.object(frappe, "get_doc", return_value=doc):
            PocketMoneyService.restore_allocation(SAMPLE_USER, "pm-001")
            self.assertTrue(doc.is_active)


class TestGetBalance(ServiceTestCase):

    def test_balance_computes_remaining(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(500,)]):
            result = PocketMoneyService.get_balance(SAMPLE_USER, "dep-son-001")
            self.assertIsNotNone(result)
            self.assertEqual(result["remaining_amount"], 1500)

    def test_balance_returns_none_when_no_allocation(self):
        with patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=None):
            result = PocketMoneyService.get_balance(SAMPLE_USER, "dep-son-001")
            self.assertIsNone(result)


class TestGetPeriodEndDate(ServiceTestCase):

    def test_weekly(self):
        from frappe.utils import add_days, getdate
        result = PocketMoneyService.get_period_end_date("2026-07-01", "Weekly")
        self.assertEqual(result, add_days(getdate("2026-07-01"), 6))

    def test_monthly(self):
        from frappe.utils import add_days, add_months, getdate
        result = PocketMoneyService.get_period_end_date("2026-07-15", "Monthly")
        expected = add_days(add_months(getdate("2026-07-15"), 1), -1)
        self.assertEqual(result, expected)


class TestBuildLowBalanceMessages(ServiceTestCase):

    @patch.object(PocketMoneyService, "get_balance", return_value=None)
    @patch("expense_manager.services.pocket_money_service.DependentService")
    def test_empty_when_no_balances(self, mock_ds, _mock_bal):
        mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
        self.assertEqual(PocketMoneyService.build_low_balance_messages("user1"), [])

    @patch.object(PocketMoneyService, "get_balance", return_value={"allocated_amount": 1000, "remaining_amount": 800})
    @patch("expense_manager.services.pocket_money_service.DependentService")
    def test_empty_when_balance_high(self, mock_ds, _mock_bal):
        mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
        self.assertEqual(PocketMoneyService.build_low_balance_messages("user1"), [])

    @patch.object(PocketMoneyService, "get_balance", return_value={"allocated_amount": 1000, "remaining_amount": 100})
    @patch("expense_manager.services.pocket_money_service.DependentService")
    def test_message_when_low(self, mock_ds, _mock_bal):
        mock_ds.list_dependents.return_value = [{"name": "d1", "dependent_name": "Son"}]
        msgs = PocketMoneyService.build_low_balance_messages("user1")
        self.assertEqual(len(msgs), 1)
        self.assertIn("running low", msgs[0])
