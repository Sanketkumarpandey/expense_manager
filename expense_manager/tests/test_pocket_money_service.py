"""Unit tests for PocketMoneyService."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.exceptions import (
    PocketMoneyAllocationNotFoundError,
    PocketMoneyAllocationAlreadyExistsError,
    PocketMoneyNotAllocatedError,
    PocketMoneyExceededError,
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

    def test_create_zero_amount_succeeds(self):
        doc = self._make_doc(allocated_amount=0.0)
        with patch.object(frappe, "get_doc", return_value=doc), \
             patch.object(frappe.db, "exists", return_value=None):
            result = PocketMoneyService.create_allocation(
                SAMPLE_USER, "dep-son-001", 0, "Monthly"
            )
            self.assertEqual(result.allocated_amount, 0.0)

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

    def test_balance_includes_total_savings(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = MagicMock()
        dep_doc.guardian = SAMPLE_USER
        dep_doc.total_savings = 750.0
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(500,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc):
            result = PocketMoneyService.get_balance(SAMPLE_USER, "dep-son-001")
            self.assertIsNotNone(result)
            self.assertEqual(result["total_savings"], 750.0)


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


class TestRolloverZeroBalance(ServiceTestCase):
    """Fix B: zero-balance rollover creates a 0-amount allocation so
    get_balance returns a valid dict (not None)."""

    def test_zero_balance_rollover_creates_allocation(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = MagicMock()
        dep_doc.allow_carry_forward = True
        dep_doc.default_monthly_allowance = 2000.0
        # Simulate remaining = 0 (2000 allocated - 2000 spent)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(2000,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation") as mock_create:
            try:
                PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            except Exception:
                pass
            mock_create.assert_called_once()
            _, kwargs = mock_create.call_args
            allocated = kwargs["allocated_amount"]
            self.assertEqual(allocated, 0.0)
            # allocated_amount is 0.0, NOT default_monthly_allowance
            self.assertNotEqual(allocated, dep_doc.default_monthly_allowance)

    def test_get_balance_returns_dict_after_zero_rollover(self):
        zero_doc = MagicMock()
        zero_doc.name = "pm-zero-001"
        zero_doc.allocated_amount = 0.0
        zero_doc.carry_forward_amount = 0.0
        zero_doc.allocation_date = "2026-07-01"
        zero_doc.allocation_period = "Monthly"
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=zero_doc), \
             patch.object(frappe.db, "sql", return_value=[(0,)]):
            result = PocketMoneyService.get_balance(SAMPLE_USER, "dep-son-001")
            self.assertIsNotNone(result)
            self.assertEqual(result["remaining_amount"], 0.0)
            self.assertEqual(result["allocated_amount"], 0.0)


class TestRolloverSavingsLedger(ServiceTestCase):
    """Unused balance rolls into the dependent's total_savings ledger
    (roadmap phase 24), separate from the spendable allocation. The new
    allocation carries forward nothing."""

    PENDING_DATE = "2026-07-27"

    def _dep_doc(self, total_savings=0.0, allow_carry_forward=True):
        dep_doc = MagicMock()
        dep_doc.allow_carry_forward = allow_carry_forward
        dep_doc.default_monthly_allowance = 2000.0
        dep_doc.total_savings = total_savings
        dep_doc.pending_allocation_since = None
        dep_doc.get = lambda key, default=None, _d=dep_doc: getattr(_d, key, default)
        return dep_doc

    def test_rollover_moves_remaining_to_savings(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = self._dep_doc()
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(500,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation") as mock_create:
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            self.assertEqual(dep_doc.total_savings, 1500.0)
            self.assertEqual(dep_doc.pending_allocation_since, self.PENDING_DATE)
            _, kwargs = mock_create.call_args
            self.assertEqual(kwargs["allocated_amount"], 0.0)
            self.assertEqual(kwargs["carry_forward_amount"], 0.0)

    def test_savings_accumulate_across_rollovers(self):
        dep_doc = self._dep_doc()

        # First rollover: 2000 allocated - 500 spent = 1500 into savings
        doc1 = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc1), \
             patch.object(frappe.db, "sql", return_value=[(500,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation"):
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
        self.assertEqual(dep_doc.total_savings, 1500.0)

        # Second rollover: new allocation with 2000 allocated - 1850 spent = 150 more
        doc2 = self._make_doc(**SAMPLE_ALLOCATION)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc2), \
             patch.object(frappe.db, "sql", return_value=[(1850,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation"):
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
        self.assertEqual(dep_doc.total_savings, 1650.0)

    def test_zero_balance_rollover_does_not_touch_savings(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = self._dep_doc(total_savings=500.0)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(2000,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation") as mock_create:
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            self.assertEqual(dep_doc.total_savings, 500.0)
            _, kwargs = mock_create.call_args
            self.assertEqual(kwargs["allocated_amount"], 0.0)
            self.assertEqual(kwargs["carry_forward_amount"], 0.0)

    def test_rollover_forfeits_when_carry_forward_disabled(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = self._dep_doc(allow_carry_forward=False)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(500,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation") as mock_create:
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            self.assertEqual(dep_doc.total_savings, 0.0)
            _, kwargs = mock_create.call_args
            self.assertEqual(kwargs["carry_forward_amount"], 0.0)


class TestPocketMoneyAllocationDocTypeValidation(TestCase):
    """Regression guard: the DocType controller must accept the zero-amount
    allocation created by PocketMoneyService.rollover_allocation (a rolled-over
    period awaiting top-up) while still rejecting negative amounts. Uses a
    plain TestCase so the controller runs against its real validation."""

    def _make_allocation_doc(self, allocated_amount):
        return frappe.get_doc(
            {
                "doctype": "Pocket Money Allocation",
                "dependent": "dep-rollover-regression",
                "allocated_amount": allocated_amount,
                "allocation_date": frappe.utils.today(),
                "allocation_period": "Monthly",
                "carry_forward_amount": 0.0,
                "total_available_amount": allocated_amount,
                "is_active": 1,
            }
        )

    def test_zero_amount_allocation_validates(self):
        doc = self._make_allocation_doc(0.0)
        with patch.object(frappe, "get_all", return_value=[]):
            doc.validate()
        self.assertEqual(doc.allocated_amount, 0.0)

    def test_negative_amount_rejected(self):
        doc = self._make_allocation_doc(-5.0)
        with patch.object(frappe, "get_all", return_value=[]):
            with self.assertRaises(frappe.ValidationError):
                doc.validate()


class TestPendingAllocationReminders(ServiceTestCase):
    """Pending-allocation reminder fields and daily job helpers."""

    PENDING_DATE = "2026-07-27"

    def _dep_mock(self, pending_allocation_since=None, total_savings=0.0):
        dep_doc = MagicMock()
        dep_doc.allow_carry_forward = True
        dep_doc.default_monthly_allowance = 2000.0
        dep_doc.total_savings = total_savings
        dep_doc.pending_allocation_since = pending_allocation_since
        dep_doc.get = lambda key, default=None, _a={
            "pending_allocation_since": pending_allocation_since,
        }: _a.get(key, default)
        return dep_doc

    def test_rollover_sets_pending_allocation_since(self):
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = self._dep_mock(pending_allocation_since=None)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(500,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation"):
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            self.assertEqual(dep_doc.pending_allocation_since, self.PENDING_DATE)

    def test_rollover_does_not_overwrite_pending_allocation_since(self):
        earlier = "2026-07-15"
        doc = self._make_doc(**SAMPLE_ALLOCATION)
        dep_doc = self._dep_mock(pending_allocation_since=earlier)
        with patch.object(PocketMoneyService, "_validate_dependent"), \
             patch.object(PocketMoneyService, "_get_active_allocation_for_dependent", return_value=doc), \
             patch.object(frappe.db, "sql", return_value=[(2000,)]), \
             patch("expense_manager.services.pocket_money_service.DependentService.get_dependent", return_value=dep_doc), \
             patch.object(PocketMoneyService, "create_allocation"):
            PocketMoneyService.rollover_allocation(SAMPLE_USER, "dep-son-001")
            self.assertEqual(dep_doc.pending_allocation_since, earlier)

    def test_create_allocation_clears_pending_allocation_since(self):
        dep_doc = MagicMock()
        dep_doc.pending_allocation_since = "2026-07-25"
        with patch("expense_manager.services.pocket_money_service.DependentService.get_dependent",
                    return_value=dep_doc), \
             patch.object(PocketMoneyService, "_clear_pending_allocation_on_dependent") as mock_clear:
            doc = self._make_doc(**SAMPLE_ALLOCATION)
            with patch.object(frappe, "get_doc", return_value=doc), \
                 patch.object(frappe.db, "exists", return_value=None):
                PocketMoneyService.create_allocation(
                    SAMPLE_USER, "dep-son-001", 2000, "Monthly"
                )
                mock_clear.assert_called_once_with("dep-son-001")

    def test_create_allocation_zero_amount_does_not_clear_pending(self):
        dep_doc = MagicMock()
        dep_doc.pending_allocation_since = "2026-07-25"
        with patch("expense_manager.services.pocket_money_service.DependentService.get_dependent",
                    return_value=dep_doc), \
             patch.object(PocketMoneyService, "_clear_pending_allocation_on_dependent") as mock_clear:
            doc = self._make_doc(**SAMPLE_ALLOCATION)
            with patch.object(frappe, "get_doc", return_value=doc), \
                 patch.object(frappe.db, "exists", return_value=None):
                PocketMoneyService.create_allocation(
                    SAMPLE_USER, "dep-son-001", 0, "Monthly"
                )
                mock_clear.assert_not_called()

    @patch.object(frappe, "get_all")
    def test_list_dependents_pending_allocation(self, mock_get_all):
        mock_get_all.return_value = [
            {
                "name": "dep-son-001",
                "dependent_name": "Son",
                "guardian": SAMPLE_USER,
                "total_savings": 500.0,
                "pending_allocation_since": "2026-07-27",
                "last_allocation_reminder_on": None,
            }
        ]
        result = PocketMoneyService.list_dependents_pending_allocation()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "dep-son-001")
        mock_get_all.assert_called_once_with(
            "Dependent",
            filters={"is_active": 1, "pending_allocation_since": ["is", "set"]},
            fields=[
                "name", "dependent_name", "guardian",
                "total_savings", "pending_allocation_since",
                "last_allocation_reminder_on",
            ],
        )

    def _dep_with_get(self, **attrs):
        dep_doc = MagicMock()
        for k, v in attrs.items():
            setattr(dep_doc, k, v)
        dep_doc.get = lambda key, default=None, _a=attrs: _a.get(key, default)
        return dep_doc

    def test_try_claim_reminder_returns_true_when_not_sent_today(self):
        dep_doc = self._dep_with_get(
            pending_allocation_since="2026-07-26",
            last_allocation_reminder_on=None,
        )
        with patch.object(frappe, "get_doc", return_value=dep_doc):
            result = PocketMoneyService.try_claim_pending_allocation_reminder("dep-son-001")
            self.assertTrue(result)
            self.assertEqual(dep_doc.last_allocation_reminder_on, self.PENDING_DATE)

    def test_try_claim_reminder_returns_false_already_sent_today(self):
        dep_doc = self._dep_with_get(
            pending_allocation_since="2026-07-26",
            last_allocation_reminder_on=self.PENDING_DATE,
        )
        with patch.object(frappe, "get_doc", return_value=dep_doc):
            result = PocketMoneyService.try_claim_pending_allocation_reminder("dep-son-001")
            self.assertFalse(result)

    def test_try_claim_reminder_returns_false_not_pending(self):
        dep_doc = self._dep_with_get(
            pending_allocation_since=None,
            last_allocation_reminder_on=None,
        )
        with patch.object(frappe, "get_doc", return_value=dep_doc):
            result = PocketMoneyService.try_claim_pending_allocation_reminder("dep-son-001")
            self.assertFalse(result)

    def test_clear_pending_allocation_on_dependent(self):
        dep_doc = self._dep_with_get(
            pending_allocation_since="2026-07-26",
            last_allocation_reminder_on="2026-07-26",
        )
        with patch.object(frappe, "get_doc", return_value=dep_doc):
            PocketMoneyService._clear_pending_allocation_on_dependent("dep-son-001")
            self.assertIsNone(dep_doc.pending_allocation_since)
            self.assertIsNone(dep_doc.last_allocation_reminder_on)
            dep_doc.save.assert_called_once_with(ignore_permissions=True)


class TestEnforceAvailableBalance(ServiceTestCase):
    """Hard-block: enforce_available_balance gates expense creation on the
    dependent's live pocket money balance."""

    def test_no_active_allocation_raises(self):
        with patch.object(PocketMoneyService, "get_balance", return_value=None):
            with self.assertRaises(PocketMoneyNotAllocatedError):
                PocketMoneyService.enforce_available_balance(SAMPLE_USER, "dep-son-001", 100)

    def test_insufficient_balance_raises(self):
        with patch.object(PocketMoneyService, "get_balance", return_value={"available_amount": 50.0}):
            with self.assertRaises(PocketMoneyExceededError):
                PocketMoneyService.enforce_available_balance(SAMPLE_USER, "dep-son-001", 100)

    def test_exact_balance_passes(self):
        with patch.object(PocketMoneyService, "get_balance", return_value={"available_amount": 100.0}):
            PocketMoneyService.enforce_available_balance(SAMPLE_USER, "dep-son-001", 100)

    def test_sufficient_balance_passes(self):
        with patch.object(PocketMoneyService, "get_balance", return_value={"available_amount": 200.0}):
            PocketMoneyService.enforce_available_balance(SAMPLE_USER, "dep-son-001", 100)
