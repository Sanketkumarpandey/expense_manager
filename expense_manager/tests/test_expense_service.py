"""Unit tests for ExpenseService."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock, patch

import frappe
from frappe.utils import getdate

from expense_manager.constants.expense import ExpenseSource
from expense_manager.services.exceptions import (
	CategoryNotAllowedError,
	ExpenseNotFoundError,
	InvalidExpenseAmountError,
	InvalidExpenseDateError,
	InvalidExpenseSourceError,
)
from expense_manager.services.expense_service import _UNSET, ExpenseService
from expense_manager.tests.base import (
	SAMPLE_CATEGORY,
	SAMPLE_DEPENDENT,
	SAMPLE_EXPENSE,
	SAMPLE_USER,
	SAMPLE_USER_2,
	ServiceTestCase,
)

Svc = ExpenseService


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _mock_category_service():
	"""Return a patch context manager for CategoryService.get_category."""
	category_doc = MagicMock()
	category_doc.name = SAMPLE_CATEGORY["name"]
	category_doc.category_name = SAMPLE_CATEGORY["category_name"]
	category_doc.owner_user = SAMPLE_CATEGORY["owner_user"]
	return patch(
		"expense_manager.services.expense_service.CategoryService.get_category",
		return_value=category_doc,
	)


def _mock_dependent_service():
	"""Return a patch context manager for DependentService.get_dependent."""
	return patch(
		"expense_manager.services.expense_service.DependentService.get_dependent",
		return_value=SAMPLE_DEPENDENT,
	)


def _mock_dependent_allowed():
	"""Return a patch context manager for DependentService.list_allowed_categories.

	Defaults to allowing the sample category, matching the "empty allowed
	list means everything is allowed" fallback.
	"""
	return patch(
		"expense_manager.services.expense_service.DependentService.list_allowed_categories",
		return_value=[SAMPLE_CATEGORY],
	)


def _mock_budget_refresh():
	"""Return a patch context manager for BudgetService.refresh_budget."""
	return patch(
		"expense_manager.services.expense_service.BudgetService.refresh_budget",
	)


def _mock_pocket_money_refresh():
	"""Return a patch context manager for PocketMoneyService.refresh_balance."""
	return patch(
		"expense_manager.services.expense_service.PocketMoneyService.refresh_balance",
	)


def _patch_all():
	"""Return a combined context manager that patches all five service dependencies."""
	from contextlib import ExitStack

	class _Combined:
		"""Context manager that groups multiple patches."""

		def __init__(self):
			self._stack = ExitStack()
			self.category = None
			self.dependent = None
			self.budget = None
			self.pocket_money = None

		def __enter__(self):
			self.category = self._stack.enter_context(_mock_category_service())
			self.dependent = self._stack.enter_context(_mock_dependent_service())
			self.allowed = self._stack.enter_context(_mock_dependent_allowed())
			self.budget = self._stack.enter_context(_mock_budget_refresh())
			self.pocket_money = self._stack.enter_context(_mock_pocket_money_refresh())
			return self

		def __exit__(self, *exc):
			return self._stack.__exit__(*exc)

	return _Combined()


def _future_date() -> str:
	"""Return a date string that is one day in the future."""
	return (getdate(frappe.utils.today()) + timedelta(days=1)).isoformat()


def _past_date() -> str:
	"""Return a date string that is one day in the past."""
	return (getdate(frappe.utils.today()) - timedelta(days=1)).isoformat()


def _today_str() -> str:
	"""Return today's date as an ISO string."""
	return frappe.utils.today()


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------


class TestCreateExpense(ServiceTestCase):
	"""Tests for ExpenseService.create_expense."""

	def test_create_expense_happy_path(self) -> None:
		"""Create an expense with all required fields and verify document creation."""
		created_doc = MagicMock()
		created_doc.name = "exp-new-001"

		with _patch_all() as _mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc) as create_doc_mock:
				result = Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=500.0,
					expense_date=_past_date(),
				)

		self.assertEqual(result, created_doc)
		create_doc_mock.assert_called_once()
		fields = create_doc_mock.call_args[0][0]
		self.assertEqual(fields["owner_user"], SAMPLE_USER)
		self.assertEqual(fields["category"], SAMPLE_CATEGORY["name"])
		self.assertEqual(fields["amount"], 500.0)
		self.assertEqual(fields["source"], ExpenseSource.MANUAL)

	def test_create_expense_with_all_optional_fields(self) -> None:
		"""Create an expense passing every optional parameter."""
		created_doc = MagicMock()
		created_doc.name = "exp-full-001"

		with _patch_all():
			with patch.object(Svc, "_create_doc", return_value=created_doc) as create_doc_mock:
				result = Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.50,
					expense_date=_past_date(),
					dependent=SAMPLE_DEPENDENT["name"],
					description="Dinner out",
					source=ExpenseSource.TELEGRAM,
					payment_method="UPI",
					voice_transcript="Spent one hundred",
				)

		self.assertEqual(result, created_doc)
		fields = create_doc_mock.call_args[0][0]
		self.assertEqual(fields["dependent"], SAMPLE_DEPENDENT["name"])
		self.assertEqual(fields["description"], "Dinner out")
		self.assertEqual(fields["source"], ExpenseSource.TELEGRAM)
		self.assertEqual(fields["payment_method"], "UPI")
		self.assertEqual(fields["voice_transcript"], "Spent one hundred")

	def test_create_expense_without_dependent(self) -> None:
		"""Create an expense with dependent=None (no dependent validation)."""
		created_doc = MagicMock()
		created_doc.name = "exp-nodp-001"

		with _patch_all() as mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=50.0,
					expense_date=_past_date(),
					dependent=None,
				)

		mocks.dependent.assert_not_called()

	def test_create_expense_refreshes_budget(self) -> None:
		"""BudgetService.refresh_budget is called after successful creation."""
		created_doc = MagicMock()
		created_doc.name = "exp-bud-001"

		with _patch_all() as mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=300.0,
					expense_date=_past_date(),
				)

		mocks.budget.assert_called_once_with(SAMPLE_USER, SAMPLE_CATEGORY["name"], dependent=None)

	def test_create_expense_refreshes_pocket_money(self) -> None:
		"""PocketMoneyService.refresh_balance is called after successful creation."""
		created_doc = MagicMock()
		created_doc.name = "exp-pm-001"

		with _patch_all() as mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=200.0,
					expense_date=_past_date(),
					dependent=SAMPLE_DEPENDENT["name"],
				)

		mocks.pocket_money.assert_called_once_with(SAMPLE_USER, SAMPLE_DEPENDENT["name"])

	def test_create_expense_allows_allowed_category_for_dependent(self) -> None:
		"""A dependent expense in an allowed category is accepted."""
		created_doc = MagicMock()
		created_doc.name = "exp-allow-001"

		with _patch_all() as mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_past_date(),
					dependent=SAMPLE_DEPENDENT["name"],
				)

		mocks.allowed.assert_called_once_with(SAMPLE_USER, SAMPLE_DEPENDENT["name"], active_only=True)

	def test_create_expense_rejects_disallowed_category_for_dependent(self) -> None:
		"""A dependent expense in a category outside the allowed list is blocked."""
		other_category = {
			"name": "cat-other-001",
			"category_name": "Other",
			"icon": "📦",
			"owner_user": SAMPLE_USER,
			"is_active": 1,
		}

		with _patch_all() as mocks:
			mocks.allowed.return_value = [other_category]
			with self.assertRaises(CategoryNotAllowedError) as ctx:
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_past_date(),
					dependent=SAMPLE_DEPENDENT["name"],
				)
			self.assertIn("not allowed", str(ctx.exception))

	def test_create_expense_allowed_check_skipped_without_dependent(self) -> None:
		"""Guardian expenses with no dependent are never run through the list."""
		created_doc = MagicMock()
		created_doc.name = "exp-nodp-002"

		with _patch_all() as mocks:
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_past_date(),
				)

		mocks.allowed.assert_not_called()

	def test_create_expense_propagates_invalid_category(self) -> None:
		"""Invalid category raises the error from CategoryService."""
		with _patch_all() as mocks:
			mocks.category.side_effect = Exception("Category not found")
			with self.assertRaises(Exception) as ctx:
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category="bad-cat",
					amount=100.0,
					expense_date=_past_date(),
				)
			self.assertIn("Category not found", str(ctx.exception))

	def test_create_expense_propagates_invalid_dependent(self) -> None:
		"""Invalid dependent raises the error from DependentService."""
		with _patch_all() as mocks:
			mocks.dependent.side_effect = Exception("Dependent not found")
			with self.assertRaises(Exception) as ctx:
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_past_date(),
					dependent="bad-dep",
				)
			self.assertIn("Dependent not found", str(ctx.exception))

	def test_create_expense_invalid_amount_zero(self) -> None:
		"""Zero amount raises InvalidExpenseAmountError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseAmountError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=0,
					expense_date=_past_date(),
				)

	def test_create_expense_invalid_amount_negative(self) -> None:
		"""Negative amount raises InvalidExpenseAmountError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseAmountError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=-50.0,
					expense_date=_past_date(),
				)

	def test_create_expense_invalid_amount_none(self) -> None:
		"""None amount raises InvalidExpenseAmountError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseAmountError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=None,
					expense_date=_past_date(),
				)

	def test_create_expense_invalid_amount_string(self) -> None:
		"""Non-numeric string amount raises InvalidExpenseAmountError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseAmountError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount="abc",
					expense_date=_past_date(),
				)

	def test_create_expense_future_date_rejected(self) -> None:
		"""Future expense date raises InvalidExpenseDateError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseDateError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_future_date(),
				)

	def test_create_expense_invalid_date_rejected(self) -> None:
		"""Unparseable date string raises InvalidExpenseDateError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseDateError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date="not-a-date",
				)

	def test_create_expense_invalid_source_rejected(self) -> None:
		"""Source not in ExpenseSource enum raises InvalidExpenseSourceError."""
		with _patch_all():
			with self.assertRaises(InvalidExpenseSourceError):
				Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_past_date(),
					source="WhatsApp",
				)

	def test_create_expense_accepts_today_date(self) -> None:
		"""Today's date is valid (not in the future)."""
		created_doc = MagicMock()
		created_doc.name = "exp-today-001"

		with _patch_all():
			with patch.object(Svc, "_create_doc", return_value=created_doc):
				result = Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount=100.0,
					expense_date=_today_str(),
				)

		self.assertEqual(result, created_doc)

	def test_create_expense_accepts_string_amount(self) -> None:
		"""Numeric string amount is coerced to float and accepted."""
		created_doc = MagicMock()
		created_doc.name = "exp-str-amt-001"

		with _patch_all():
			with patch.object(Svc, "_create_doc", return_value=created_doc) as create_doc_mock:
				result = Svc.create_expense(
					owner_user=SAMPLE_USER,
					category=SAMPLE_CATEGORY["name"],
					amount="150.75",
					expense_date=_past_date(),
				)

		self.assertEqual(result, created_doc)
		fields = create_doc_mock.call_args[0][0]
		self.assertEqual(fields["amount"], 150.75)

	def test_create_expense_all_valid_sources_accepted(self) -> None:
		"""All ExpenseSource enum values are accepted as valid sources."""
		for source in ExpenseSource:
			created_doc = MagicMock()
			created_doc.name = f"exp-src-{source.value}"

			with _patch_all():
				with patch.object(Svc, "_create_doc", return_value=created_doc):
					result = Svc.create_expense(
						owner_user=SAMPLE_USER,
						category=SAMPLE_CATEGORY["name"],
						amount=100.0,
						expense_date=_past_date(),
						source=source,
					)

			self.assertEqual(result, created_doc)


# ------------------------------------------------------------------
# Get
# ------------------------------------------------------------------


class TestGetExpense(ServiceTestCase):
	"""Tests for ExpenseService.get_expense."""

	def test_get_expense_happy_path(self) -> None:
		"""Retrieve an existing expense owned by the requesting user."""
		mock_expense = self._make_doc()

		with patch.object(Svc, "_get_expense", return_value=mock_expense):
			result = Svc.get_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"])

		self.assertEqual(result, mock_expense)

	def test_get_expense_not_found(self) -> None:
		"""Non-existent expense ID raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.get_expense(SAMPLE_USER, "nonexistent-id")

	def test_get_expense_wrong_owner(self) -> None:
		"""Expense belonging to another user raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.get_expense(SAMPLE_USER_2, SAMPLE_EXPENSE["name"])


# ------------------------------------------------------------------
# _get_expense (ownership check)
# ------------------------------------------------------------------


class TestGetExpenseInternal(ServiceTestCase):
	"""Tests for ExpenseService._get_expense ownership enforcement."""

	def test_returns_doc_when_owner_matches(self) -> None:
		"""_get_expense returns the document when owner_user matches."""
		mock_doc = MagicMock()
		mock_doc.owner_user = SAMPLE_USER

		with patch("frappe.get_doc", return_value=mock_doc):
			result = Svc._get_expense(SAMPLE_USER, "exp-001")

		self.assertEqual(result, mock_doc)

	def test_raises_when_expense_does_not_exist(self) -> None:
		"""_get_expense raises ExpenseNotFoundError when frappe.get_doc raises DoesNotExistError."""
		with patch("frappe.get_doc", side_effect=frappe.DoesNotExistError):
			with self.assertRaises(ExpenseNotFoundError):
				Svc._get_expense(SAMPLE_USER, "nonexistent-id")

	def test_raises_when_owner_mismatch(self) -> None:
		"""_get_expense raises ExpenseNotFoundError when owner_user does not match."""
		mock_doc = MagicMock()
		mock_doc.owner_user = SAMPLE_USER_2

		with patch("frappe.get_doc", return_value=mock_doc):
			with self.assertRaises(ExpenseNotFoundError):
				Svc._get_expense(SAMPLE_USER, "exp-001")


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------


class TestUpdateExpense(ServiceTestCase):
	"""Tests for ExpenseService.update_expense."""

	def _patch_get_expense(self, doc=None):
		"""Patch _get_expense to return a mock document."""
		if doc is None:
			doc = self._make_doc()
		return patch.object(Svc, "_get_expense", return_value=doc)

	def test_update_category(self) -> None:
		"""Updating category changes the doc category and refreshes budgets."""
		doc = self._make_doc(category="cat-old")

		with _patch_all() as mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], category="cat-new")

		self.assertEqual(doc.category, "cat-new")
		doc.save.assert_called_once()
		mocks.budget.assert_any_call(SAMPLE_USER, "cat-old", dependent=None)
		mocks.budget.assert_any_call(SAMPLE_USER, "cat-new", dependent=None)

	def test_update_category_none_does_not_change(self) -> None:
		"""Passing category=None does not modify the existing category."""
		doc = self._make_doc(category="cat-original")

		with _patch_all() as _mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], category=None)

		self.assertEqual(doc.category, "cat-original")
		doc.save.assert_called_once()

	def test_update_amount(self) -> None:
		"""Updating amount changes the doc amount."""
		doc = self._make_doc(amount=100.0)

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], amount=750.0)

		self.assertEqual(doc.amount, 750.0)
		doc.save.assert_called_once()

	def test_update_expense_date(self) -> None:
		"""Updating expense_date changes the doc date."""
		doc = self._make_doc(expense_date=_past_date())

		with _patch_all():
			with self._patch_get_expense(doc):
				new_date = (getdate(frappe.utils.today()) - timedelta(days=5)).isoformat()
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], expense_date=new_date)

		self.assertEqual(doc.expense_date, new_date)

	def test_update_dependent_unset_keeps_existing(self) -> None:
		"""_UNSET sentinel does not change the existing dependent."""
		doc = self._make_doc(dependent="dep-old")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], dependent=_UNSET)

		self.assertEqual(doc.dependent, "dep-old")

	def test_update_dependent_none_clears(self) -> None:
		"""Passing dependent=None clears the dependent field."""
		doc = self._make_doc(dependent="dep-old")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], dependent=None)

		self.assertIsNone(doc.dependent)

	def test_update_dependent_new_validates_and_sets(self) -> None:
		"""Passing a new dependent name validates it and sets the field."""
		doc = self._make_doc(dependent="dep-old")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(
					SAMPLE_USER,
					SAMPLE_EXPENSE["name"],
					dependent=SAMPLE_DEPENDENT["name"],
				)

		self.assertEqual(doc.dependent, SAMPLE_DEPENDENT["name"])

	def test_update_description_unset_keeps_existing(self) -> None:
		"""_UNSET sentinel does not change the existing description."""
		doc = self._make_doc(description="old desc")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], description=_UNSET)

		self.assertEqual(doc.description, "old desc")

	def test_update_description_none_clears(self) -> None:
		"""Passing description=None clears the description."""
		doc = self._make_doc(description="old desc")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], description=None)

		self.assertIsNone(doc.description)

	def test_update_payment_method_unset_keeps_existing(self) -> None:
		"""_UNSET sentinel does not change the existing payment_method."""
		doc = self._make_doc(payment_method="Cash")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], payment_method=_UNSET)

		self.assertEqual(doc.payment_method, "Cash")

	def test_update_payment_method_none_clears(self) -> None:
		"""Passing payment_method=None clears it."""
		doc = self._make_doc(payment_method="Cash")

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], payment_method=None)

		self.assertIsNone(doc.payment_method)

	def test_update_no_changes_still_saves(self) -> None:
		"""Calling update with no field changes still saves and refreshes budgets."""
		doc = self._make_doc()

		with _patch_all():
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"])

		doc.save.assert_called_once()

	def test_update_refreshes_old_budget_when_category_unchanged(self) -> None:
		"""Budget refresh is called for old category even when category is not changed."""
		doc = self._make_doc(category="cat-same")

		with _patch_all() as mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], amount=999.0)

		mocks.budget.assert_called_once_with(SAMPLE_USER, "cat-same", dependent=None)

	def test_update_refreshes_both_budgets_on_category_change(self) -> None:
		"""Both old and new category budgets are refreshed when category changes."""
		doc = self._make_doc(category="cat-old")

		with _patch_all() as mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], category="cat-new")

		calls = [c for c in mocks.budget.call_args_list]
		self.assertEqual(len(calls), 2)
		self.assertEqual(calls[0].args, (SAMPLE_USER, "cat-old"))
		self.assertEqual(calls[0].kwargs, {"dependent": None})
		self.assertEqual(calls[1].args, (SAMPLE_USER, "cat-new"))
		self.assertEqual(calls[1].kwargs, {"dependent": None})

	def test_update_refreshes_pocket_money_on_dependent_change(self) -> None:
		"""Both old and new dependent pocket money are refreshed on change."""
		doc = self._make_doc(dependent="dep-old")

		with _patch_all() as mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(
					SAMPLE_USER,
					SAMPLE_EXPENSE["name"],
					dependent="dep-new",
				)

		calls = [c for c in mocks.pocket_money.call_args_list]
		self.assertEqual(len(calls), 2)
		self.assertEqual(calls[0].args, (SAMPLE_USER, "dep-old"))
		self.assertEqual(calls[1].args, (SAMPLE_USER, "dep-new"))

	def test_update_refreshes_pocket_money_when_dependent_unchanged(self) -> None:
		"""Pocket money refresh is called once with old dependent when dependent is unchanged."""
		doc = self._make_doc(dependent="dep-same")

		with _patch_all() as mocks:
			with self._patch_get_expense(doc):
				Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], amount=500.0)

		mocks.pocket_money.assert_called_once_with(SAMPLE_USER, "dep-same")

	def test_update_rejects_disallowed_category_for_dependent(self) -> None:
		"""Updating a dependent expense to a disallowed category is blocked."""
		other_category = {
			"name": "cat-other-001",
			"category_name": "Other",
			"icon": "📦",
			"owner_user": SAMPLE_USER,
			"is_active": 1,
		}
		doc = self._make_doc(dependent=SAMPLE_DEPENDENT["name"])

		with _patch_all() as mocks:
			mocks.allowed.return_value = [other_category]
			with self._patch_get_expense(doc):
				with self.assertRaises(CategoryNotAllowedError):
					Svc.update_expense(
						SAMPLE_USER,
						SAMPLE_EXPENSE["name"],
						category="cat-new",
					)

	def test_update_rejects_allowed_category_for_disallowed_dependent(self) -> None:
		"""Reassigning an expense to a dependent whose allowed list excludes
		the expense's existing category is blocked."""
		other_category = {
			"name": "cat-other-001",
			"category_name": "Other",
			"icon": "📦",
			"owner_user": SAMPLE_USER,
			"is_active": 1,
		}
		doc = self._make_doc(
			dependent=SAMPLE_DEPENDENT["name"],
			category=SAMPLE_CATEGORY["name"],
		)

		with _patch_all() as mocks:
			mocks.allowed.return_value = [other_category]
			with self._patch_get_expense(doc):
				with self.assertRaises(CategoryNotAllowedError):
					Svc.update_expense(
						SAMPLE_USER,
						SAMPLE_EXPENSE["name"],
						dependent="dep-son-002",
					)

	def test_update_expense_not_found(self) -> None:
		"""Update of non-existent expense raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.update_expense(SAMPLE_USER, "bad-id", amount=100.0)

	def test_update_wrong_owner(self) -> None:
		"""Update of expense owned by another user raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.update_expense(SAMPLE_USER_2, SAMPLE_EXPENSE["name"], amount=100.0)

	def test_update_invalid_amount_zero(self) -> None:
		"""Updating with zero amount raises InvalidExpenseAmountError."""
		doc = self._make_doc()

		with _patch_all():
			with self._patch_get_expense(doc):
				with self.assertRaises(InvalidExpenseAmountError):
					Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], amount=0)

	def test_update_invalid_amount_negative(self) -> None:
		"""Updating with negative amount raises InvalidExpenseAmountError."""
		doc = self._make_doc()

		with _patch_all():
			with self._patch_get_expense(doc):
				with self.assertRaises(InvalidExpenseAmountError):
					Svc.update_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"], amount=-10)

	def test_update_future_date_rejected(self) -> None:
		"""Updating with a future date raises InvalidExpenseDateError."""
		doc = self._make_doc()

		with _patch_all():
			with self._patch_get_expense(doc):
				with self.assertRaises(InvalidExpenseDateError):
					Svc.update_expense(
						SAMPLE_USER,
						SAMPLE_EXPENSE["name"],
						expense_date=_future_date(),
					)


# ------------------------------------------------------------------
# Delete
# ------------------------------------------------------------------


class TestDeleteExpense(ServiceTestCase):
	"""Tests for ExpenseService.delete_expense."""

	def test_delete_expense_happy_path(self) -> None:
		"""Delete an existing expense owned by the requesting user."""
		doc = self._make_doc()

		with _patch_all() as _mocks:
			with patch.object(Svc, "_get_expense", return_value=doc):
				Svc.delete_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"])

		doc.delete.assert_called_once()

	def test_delete_refreshes_budget(self) -> None:
		"""BudgetService.refresh_budget is called after deletion."""
		doc = self._make_doc(category="cat-food-001")

		with _patch_all() as mocks:
			with patch.object(Svc, "_get_expense", return_value=doc):
				Svc.delete_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"])

		mocks.budget.assert_called_once_with(SAMPLE_USER, "cat-food-001", dependent=None)

	def test_delete_refreshes_pocket_money(self) -> None:
		"""PocketMoneyService.refresh_balance is called after deletion."""
		doc = self._make_doc(dependent=SAMPLE_DEPENDENT["name"])

		with _patch_all() as mocks:
			with patch.object(Svc, "_get_expense", return_value=doc):
				Svc.delete_expense(SAMPLE_USER, SAMPLE_EXPENSE["name"])

		mocks.pocket_money.assert_called_once_with(SAMPLE_USER, SAMPLE_DEPENDENT["name"])

	def test_delete_not_found(self) -> None:
		"""Deleting a non-existent expense raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.delete_expense(SAMPLE_USER, "bad-id")

	def test_delete_wrong_owner(self) -> None:
		"""Deleting an expense owned by another user raises ExpenseNotFoundError."""
		with patch.object(Svc, "_get_expense", side_effect=ExpenseNotFoundError("Expense not found.")):
			with self.assertRaises(ExpenseNotFoundError):
				Svc.delete_expense(SAMPLE_USER_2, SAMPLE_EXPENSE["name"])

	def test_delete_passes_correct_owner_to_refresh(self) -> None:
		"""Budget refresh uses the document's owner_user, not the caller."""
		doc = self._make_doc()
		doc.owner_user = SAMPLE_USER_2

		with _patch_all() as mocks:
			with patch.object(Svc, "_get_expense", return_value=doc):
				Svc.delete_expense(SAMPLE_USER_2, SAMPLE_EXPENSE["name"])

		mocks.budget.assert_called_once_with(SAMPLE_USER_2, SAMPLE_CATEGORY["name"], dependent=None)
		mocks.pocket_money.assert_called_once_with(SAMPLE_USER_2, doc.dependent)


# ------------------------------------------------------------------
# List expenses
# ------------------------------------------------------------------


class TestListExpenses(ServiceTestCase):
	"""Tests for ExpenseService.list_expenses."""

	def test_list_expenses_happy_path(self) -> None:
		"""List expenses with no filters returns all for owner_user."""
		sample_rows = [
			{"name": "exp-001", "amount": 100.0},
			{"name": "exp-002", "amount": 200.0},
		]
		with patch("frappe.get_all", return_value=sample_rows):
			result = Svc.list_expenses(SAMPLE_USER)

		self.assertEqual(result, sample_rows)

	def test_list_expenses_filters_by_owner(self) -> None:
		"""List expenses always filters by owner_user."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER)

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["owner_user"], SAMPLE_USER)

	def test_list_expenses_filters_by_category(self) -> None:
		"""Passing category adds it to the filters."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, category="cat-food-001")

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["category"], "cat-food-001")

	def test_list_expenses_filters_by_dependent(self) -> None:
		"""Passing dependent adds it to the filters."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, dependent="dep-son-001")

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["dependent"], "dep-son-001")

	def test_list_expenses_date_from_only(self) -> None:
		"""Passing only date_from creates a >= filter."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, date_from="2026-07-01")

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["expense_date"], [">=", "2026-07-01"])

	def test_list_expenses_date_to_only(self) -> None:
		"""Passing only date_to creates a <= filter."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, date_to="2026-07-31")

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["expense_date"], ["<=", "2026-07-31"])

	def test_list_expenses_date_range(self) -> None:
		"""Passing both date_from and date_to creates a between filter."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, date_from="2026-07-01", date_to="2026-07-31")

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["expense_date"], ["between", ["2026-07-01", "2026-07-31"]])

	def test_list_expenses_no_date_filters(self) -> None:
		"""Without date filters, expense_date is not in filters."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER)

		filters = get_all_mock.call_args[1]["filters"]
		self.assertNotIn("expense_date", filters)

	def test_list_expenses_limit(self) -> None:
		"""Passing limit sets limit_page_length."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER, limit=5)

		self.assertEqual(get_all_mock.call_args[1]["limit_page_length"], 5)

	def test_list_expenses_no_limit(self) -> None:
		"""Without limit, limit_page_length is 0 (no limit)."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER)

		self.assertEqual(get_all_mock.call_args[1]["limit_page_length"], 0)

	def test_list_expenses_all_filters_combined(self) -> None:
		"""Passing all filters together applies them correctly."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(
				SAMPLE_USER,
				category="cat-food-001",
				dependent="dep-son-001",
				date_from="2026-07-01",
				date_to="2026-07-31",
				limit=10,
			)

		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["owner_user"], SAMPLE_USER)
		self.assertEqual(filters["category"], "cat-food-001")
		self.assertEqual(filters["dependent"], "dep-son-001")
		self.assertEqual(filters["expense_date"], ["between", ["2026-07-01", "2026-07-31"]])
		self.assertEqual(get_all_mock.call_args[1]["limit_page_length"], 10)

	def test_list_expenses_requests_expected_fields(self) -> None:
		"""list_expenses requests all expected field columns."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER)

		fields = get_all_mock.call_args[1]["fields"]
		expected_fields = [
			"name",
			"category",
			"amount",
			"expense_date",
			"dependent",
			"description",
			"source",
			"payment_method",
			"creation",
			"modified",
		]
		self.assertEqual(fields, expected_fields)

	def test_list_expenses_order_by(self) -> None:
		"""list_expenses orders by expense_date desc, creation desc."""
		with patch("frappe.get_all", return_value=[]) as get_all_mock:
			Svc.list_expenses(SAMPLE_USER)

		self.assertEqual(
			get_all_mock.call_args[1]["order_by"],
			"expense_date desc, creation desc",
		)


class TestAttachDependentNames(ServiceTestCase):
	"""Tests for ExpenseService.attach_dependent_names."""

	def test_attach_names_resolves_live_dependent_name(self) -> None:
		"""Rows get the current dependent_name instead of a captured value."""
		rows = [
			{"name": "exp-001", "dependent": "dep-son-001"},
			{"name": "exp-002", "dependent": "dep-son-001"},
		]
		with patch(
			"frappe.get_all",
			return_value=[
				{"name": "dep-son-001", "dependent_name": "Alex Junior"},
			],
		) as get_all_mock:
			result = Svc.attach_dependent_names(rows, SAMPLE_USER)

		self.assertEqual(result[0]["dependent_name"], "Alex Junior")
		self.assertEqual(result[1]["dependent_name"], "Alex Junior")
		filters = get_all_mock.call_args[1]["filters"]
		self.assertEqual(filters["guardian"], SAMPLE_USER)

	def test_attach_names_blank_when_dependent_unknown(self) -> None:
		"""Rows referencing a dependent that no longer resolves get a blank name."""
		rows = [{"name": "exp-001", "dependent": "dep-gone-001"}]
		with patch("frappe.get_all", return_value=[]):
			result = Svc.attach_dependent_names(rows, SAMPLE_USER)

		self.assertEqual(result[0]["dependent_name"], "")

	def test_attach_names_skips_rows_without_dependent(self) -> None:
		"""Rows without a dependent are left blank without a lookup."""
		rows = [{"name": "exp-001", "dependent": None}]
		with patch("frappe.get_all") as get_all_mock:
			result = Svc.attach_dependent_names(rows, SAMPLE_USER)

		self.assertEqual(result[0]["dependent_name"], "")
		get_all_mock.assert_not_called()

	def test_attach_names_empty_rows_no_lookup(self) -> None:
		"""An empty list is returned without any lookup."""
		with patch("frappe.get_all") as get_all_mock:
			result = Svc.attach_dependent_names([], SAMPLE_USER)

		self.assertEqual(result, [])
		get_all_mock.assert_not_called()


# ------------------------------------------------------------------
# Convenience list wrappers
# ------------------------------------------------------------------


class TestConvenienceListMethods(ServiceTestCase):
	"""Tests for get_recent_expenses, get_expenses_by_category, get_expenses_by_date_range."""

	def test_get_recent_expenses_delegates_to_list(self) -> None:
		"""get_recent_expenses calls list_expenses with limit."""
		with patch.object(Svc, "list_expenses", return_value=["row1"]) as list_mock:
			result = Svc.get_recent_expenses(SAMPLE_USER, limit=5)

		list_mock.assert_called_once_with(SAMPLE_USER, dependent=None, limit=5)
		self.assertEqual(result, ["row1"])

	def test_get_recent_expenses_with_dependent(self) -> None:
		"""get_recent_expenses passes dependent filter to list_expenses."""
		with patch.object(Svc, "list_expenses", return_value=[]) as list_mock:
			Svc.get_recent_expenses(SAMPLE_USER, dependent="dep-son-001", limit=3)

		list_mock.assert_called_once_with(SAMPLE_USER, dependent="dep-son-001", limit=3)

	def test_get_recent_expenses_default_limit(self) -> None:
		"""get_recent_expenses defaults to limit=10."""
		with patch.object(Svc, "list_expenses", return_value=[]) as list_mock:
			Svc.get_recent_expenses(SAMPLE_USER)

		list_mock.assert_called_once_with(SAMPLE_USER, dependent=None, limit=10)

	def test_get_expenses_by_category_delegates_to_list(self) -> None:
		"""get_expenses_by_category calls list_expenses with category filter."""
		with patch.object(Svc, "list_expenses", return_value=["row1"]) as list_mock:
			result = Svc.get_expenses_by_category(SAMPLE_USER, "cat-food-001")

		list_mock.assert_called_once_with(SAMPLE_USER, dependent=None, category="cat-food-001")
		self.assertEqual(result, ["row1"])

	def test_get_expenses_by_category_with_dependent(self) -> None:
		"""get_expenses_by_category passes dependent to list_expenses."""
		with patch.object(Svc, "list_expenses", return_value=[]) as list_mock:
			Svc.get_expenses_by_category(SAMPLE_USER, "cat-food-001", dependent="dep-son-001")

		list_mock.assert_called_once_with(SAMPLE_USER, dependent="dep-son-001", category="cat-food-001")

	def test_get_expenses_by_date_range_delegates_to_list(self) -> None:
		"""get_expenses_by_date_range calls list_expenses with date filters."""
		with patch.object(Svc, "list_expenses", return_value=["row1"]) as list_mock:
			result = Svc.get_expenses_by_date_range(SAMPLE_USER, "2026-07-01", "2026-07-31")

		list_mock.assert_called_once_with(
			SAMPLE_USER,
			dependent=None,
			date_from="2026-07-01",
			date_to="2026-07-31",
		)
		self.assertEqual(result, ["row1"])

	def test_get_expenses_by_date_range_with_dependent(self) -> None:
		"""get_expenses_by_date_range passes dependent to list_expenses."""
		with patch.object(Svc, "list_expenses", return_value=[]) as list_mock:
			Svc.get_expenses_by_date_range(
				SAMPLE_USER,
				"2026-07-01",
				"2026-07-31",
				dependent="dep-son-001",
			)

		list_mock.assert_called_once_with(
			SAMPLE_USER,
			dependent="dep-son-001",
			date_from="2026-07-01",
			date_to="2026-07-31",
		)


# ------------------------------------------------------------------
# Validation helpers
# ------------------------------------------------------------------


class TestValidation(ServiceTestCase):
	"""Tests for the private _validate_* methods."""

	def test_validate_amount_accepts_positive(self) -> None:
		"""_validate_amount returns the float value for positive numbers."""
		self.assertEqual(Svc._validate_amount(50.0), 50.0)

	def test_validate_amount_rejects_zero(self) -> None:
		"""_validate_amount raises InvalidExpenseAmountError for zero."""
		with self.assertRaises(InvalidExpenseAmountError):
			Svc._validate_amount(0)

	def test_validate_amount_rejects_negative(self) -> None:
		"""_validate_amount raises InvalidExpenseAmountError for negative values."""
		with self.assertRaises(InvalidExpenseAmountError):
			Svc._validate_amount(-1.5)

	def test_validate_amount_rejects_none(self) -> None:
		"""_validate_amount raises InvalidExpenseAmountError for None."""
		with self.assertRaises(InvalidExpenseAmountError):
			Svc._validate_amount(None)

	def test_validate_amount_coerces_string(self) -> None:
		"""_validate_amount coerces numeric strings to float."""
		self.assertEqual(Svc._validate_amount("100.5"), 100.5)

	def test_validate_amount_rejects_non_numeric_string(self) -> None:
		"""_validate_amount raises InvalidExpenseAmountError for non-numeric strings."""
		with self.assertRaises(InvalidExpenseAmountError):
			Svc._validate_amount("hello")

	def test_validate_expense_date_rejects_none(self) -> None:
		"""_validate_expense_date raises InvalidExpenseDateError for None."""
		with self.assertRaises(InvalidExpenseDateError):
			Svc._validate_expense_date(None)

	def test_validate_expense_date_rejects_future(self) -> None:
		"""_validate_expense_date raises InvalidExpenseDateError for future dates."""
		with self.assertRaises(InvalidExpenseDateError):
			Svc._validate_expense_date(_future_date())

	def test_validate_expense_date_accepts_today(self) -> None:
		"""_validate_expense_date accepts today's date without error."""
		Svc._validate_expense_date(_today_str())

	def test_validate_expense_date_accepts_past(self) -> None:
		"""_validate_expense_date accepts past dates without error."""
		Svc._validate_expense_date(_past_date())

	def test_validate_source_accepts_valid(self) -> None:
		"""_validate_source does not raise for valid ExpenseSource values."""
		for source in ExpenseSource:
			Svc._validate_source(source)

	def test_validate_source_rejects_invalid(self) -> None:
		"""_validate_source raises InvalidExpenseSourceError for unknown values."""
		with self.assertRaises(InvalidExpenseSourceError):
			Svc._validate_source("Email")

	def test_validate_category_delegates_to_category_service(self) -> None:
		"""_validate_category calls CategoryService.get_category without dependent."""
		with patch("expense_manager.services.expense_service.CategoryService.get_category") as mock_cat:
			Svc._validate_category(SAMPLE_USER, "cat-food-001")

		mock_cat.assert_called_once_with(SAMPLE_USER, "cat-food-001")

	def test_validate_category_ignores_dependent_argument(self) -> None:
		"""_validate_category authorizes on the shared pool; dependent is not passed to CategoryService."""
		with patch("expense_manager.services.expense_service.CategoryService.get_category") as mock_cat:
			Svc._validate_category(SAMPLE_USER, "cat-food-001", dependent="dep-son-001")

		mock_cat.assert_called_once_with(SAMPLE_USER, "cat-food-001")

	def test_validate_dependent_skips_when_none(self) -> None:
		"""_validate_dependent does nothing when dependent is None."""
		with patch("expense_manager.services.expense_service.DependentService.get_dependent") as mock_dep:
			Svc._validate_dependent(SAMPLE_USER, None)

		mock_dep.assert_not_called()

	def test_validate_dependent_delegates_to_service(self) -> None:
		"""_validate_dependent calls DependentService.get_dependent for non-None."""
		with patch("expense_manager.services.expense_service.DependentService.get_dependent") as mock_dep:
			Svc._validate_dependent(SAMPLE_USER, "dep-son-001")

		mock_dep.assert_called_once_with(SAMPLE_USER, "dep-son-001")
