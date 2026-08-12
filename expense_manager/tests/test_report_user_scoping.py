"""Tests for report user scoping (F-1).

Report filters previously let a caller pass ``individual``/``guardian``
and use it as the report's identity. Reports now resolve the effective
user from the session: non-privileged sessions are always scoped to the
session user; only System Manager / Administrator may request another
guardian's data.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from expense_manager.services.report_service import ReportService
from expense_manager.tests.base import (
	SAMPLE_USER,
	SAMPLE_USER_2,
	ServiceTestCase,
)

REPORT_USER = "report_viewer@example.com"
OTHER_USER = "other_guardian@example.com"


class TestResolveReportUser(TestCase):
	def test_defaults_to_owner_user(self):
		with (
			patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)),
			patch(
				"expense_manager.services.report_service.frappe.get_roles",
				return_value=["Expense Manager User"],
			),
		):
			self.assertEqual(
				ReportService._resolve_report_user(SAMPLE_USER, None),
				SAMPLE_USER,
			)

	def test_non_privileged_session_ignores_requested_user(self):
		with (
			patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)),
			patch(
				"expense_manager.services.report_service.frappe.get_roles",
				return_value=["Expense Manager User"],
			),
		):
			self.assertEqual(
				ReportService._resolve_report_user(SAMPLE_USER, OTHER_USER),
				SAMPLE_USER,
			)

	def test_system_manager_may_request_another_user(self):
		with (
			patch.object(frappe, "session", SimpleNamespace(user=REPORT_USER)),
			patch(
				"expense_manager.services.report_service.frappe.get_roles", return_value=["System Manager"]
			),
		):
			self.assertEqual(
				ReportService._resolve_report_user(SAMPLE_USER, OTHER_USER),
				OTHER_USER,
			)

	def test_administrator_may_request_another_user(self):
		with (
			patch.object(frappe, "session", SimpleNamespace(user="Administrator")),
			patch("expense_manager.services.report_service.frappe.get_roles", return_value=["Administrator"]),
		):
			self.assertEqual(
				ReportService._resolve_report_user(SAMPLE_USER, OTHER_USER),
				OTHER_USER,
			)


class TestReportScopingNonPrivileged(ServiceTestCase):
	"""A regular viewer can never redirect a report at another user."""

	def _patch_session(self):
		self._session_patch = patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER))
		self._roles_patch = patch(
			"expense_manager.services.report_service.frappe.get_roles",
			return_value=["Expense Manager User"],
		)
		self._session_patch.start()
		self._roles_patch.start()

	def tearDown(self):
		if getattr(self, "_roles_patch", None):
			self._roles_patch.stop()
		if getattr(self, "_session_patch", None):
			self._session_patch.stop()
		super().tearDown()

	def test_expense_detail_report_scoped_to_session_user(self):
		self._patch_session()
		with (
			patch(
				"expense_manager.services.report_service.ExpenseService.list_expenses",
				return_value=[],
			) as mock_list,
			patch(
				"expense_manager.services.report_service.BudgetService.list_budgets",
				return_value=[],
			),
			patch(
				"expense_manager.services.report_service.ReportService._category_name_lookup",
				return_value={},
			),
		):
			ReportService.get_expense_detail_report(SAMPLE_USER, individual=OTHER_USER)
		self.assertEqual(mock_list.call_args[0][0], SAMPLE_USER)

	def test_category_analytics_scoped_to_session_user(self):
		self._patch_session()
		with (
			patch(
				"expense_manager.services.report_service.ReportService.get_category_breakdown",
				return_value=[],
			) as mock_breakdown,
			patch(
				"expense_manager.services.report_service.BudgetService.list_budgets",
				return_value=[],
			),
		):
			ReportService.get_category_analytics_data(SAMPLE_USER, individual=OTHER_USER)
		self.assertEqual(mock_breakdown.call_args[0][0], SAMPLE_USER)

	def test_monthly_expense_trend_scoped_to_session_user(self):
		self._patch_session()
		with patch(
			"expense_manager.services.report_service.ReportService.get_monthly_report",
			return_value=[],
		) as mock_monthly:
			ReportService.get_monthly_expense_trend_data(SAMPLE_USER, individual=OTHER_USER)
		self.assertEqual(mock_monthly.call_args[0][0], SAMPLE_USER)

	def test_guardian_overview_scoped_to_session_user(self):
		self._patch_session()
		with patch(
			"expense_manager.services.report_service.DependentService.list_dependents",
			return_value=[],
		) as mock_deps:
			ReportService.get_guardian_overview_data(SAMPLE_USER, requested_user=OTHER_USER)
		self.assertEqual(mock_deps.call_args[0][0], SAMPLE_USER)


class TestReportScopingPrivileged(ServiceTestCase):
	"""System Manager may request another guardian's data explicitly."""

	def _patch_session(self):
		self._session_patch = patch.object(frappe, "session", SimpleNamespace(user=REPORT_USER))
		self._roles_patch = patch(
			"expense_manager.services.report_service.frappe.get_roles",
			return_value=["System Manager"],
		)
		self._session_patch.start()
		self._roles_patch.start()

	def tearDown(self):
		if getattr(self, "_roles_patch", None):
			self._roles_patch.stop()
		if getattr(self, "_session_patch", None):
			self._session_patch.stop()
		super().tearDown()

	def test_expense_detail_report_honors_requested_user(self):
		self._patch_session()
		with (
			patch(
				"expense_manager.services.report_service.ExpenseService.list_expenses",
				return_value=[],
			) as mock_list,
			patch(
				"expense_manager.services.report_service.BudgetService.list_budgets",
				return_value=[],
			),
			patch(
				"expense_manager.services.report_service.ReportService._category_name_lookup",
				return_value={},
			),
		):
			ReportService.get_expense_detail_report(SAMPLE_USER, individual=OTHER_USER)
		self.assertEqual(mock_list.call_args[0][0], OTHER_USER)

	def test_guardian_overview_honors_requested_user(self):
		self._patch_session()
		with patch(
			"expense_manager.services.report_service.DependentService.list_dependents",
			return_value=[],
		) as mock_deps:
			ReportService.get_guardian_overview_data(SAMPLE_USER, requested_user=OTHER_USER)
		self.assertEqual(mock_deps.call_args[0][0], OTHER_USER)


class TestGuardianOverviewReportEntryPoint(TestCase):
	def test_execute_passes_requested_guardian_not_as_owner(self):
		from expense_manager.expense_manager.report.guardian_overview import (
			guardian_overview,
		)

		with (
			patch.object(frappe, "session", SimpleNamespace(user=SAMPLE_USER)),
			patch(
				"expense_manager.services.report_service.ReportService.get_guardian_overview_data",
				return_value=MagicMock(),
			) as mock_report,
		):
			guardian_overview.execute({"guardian": OTHER_USER})

		self.assertEqual(mock_report.call_args[0][0], SAMPLE_USER)
		self.assertEqual(mock_report.call_args[1]["requested_user"], OTHER_USER)
