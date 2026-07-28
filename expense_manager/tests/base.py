"""Shared test fixtures for Expense Manager service tests.

Every test class should inherit from ServiceTestCase to get
standardised Frappe mocks, sample data dictionaries, and common
assertion helpers.  No business logic lives here — only
boilerplate that would otherwise be duplicated across test modules.
"""

from __future__ import annotations

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe.utils


# ------------------------------------------------------------------
# Canonical sample data
# ------------------------------------------------------------------

SAMPLE_USER = "guardian@example.com"
SAMPLE_USER_2 = "guardian2@example.com"

SAMPLE_CATEGORY = {
    "name": "cat-food-001",
    "category_name": "Food",
    "icon": "🍽️",
    "owner_user": SAMPLE_USER,
    "is_active": 1,
}

SAMPLE_DEPENDENT = {
    "name": "dep-son-001",
    "dependent_name": "Son",
    "guardian": SAMPLE_USER,
    "relationship": "Son",
    "default_monthly_allowance": 2000.0,
    "telegram_username": None,
    "telegram_user_id": None,
    "allow_carry_forward": True,
    "is_active": 1,
}

SAMPLE_EXPENSE = {
    "name": "exp-001",
    "owner_user": SAMPLE_USER,
    "category": "cat-food-001",
    "amount": 250.0,
    "expense_date": "2026-07-15",
    "dependent": None,
    "description": "Lunch",
    "source": "Manual",
    "payment_method": "Cash",
    "voice_transcript": None,
}

SAMPLE_BUDGET = {
    "name": "bud-001",
    "owner_user": SAMPLE_USER,
    "category": "cat-food-001",
    "period": "Monthly",
    "start_date": "2026-07-01",
    "end_date": "2026-07-31",
    "allocated_amount": 5000.0,
    "spent_amount": 0.0,
    "alert_threshold_pct": 90,
    "is_active": 1,
    "notes": None,
}

SAMPLE_ALLOCATION = {
    "name": "pm-001",
    "dependent": "dep-son-001",
    "allocated_amount": 2000.0,
    "allocation_date": "2026-07-01",
    "allocation_period": "Monthly",
    "carry_forward_amount": 0.0,
    "total_available_amount": 2000.0,
    "remarks": None,
    "is_active": 1,
}

SAMPLE_TELEGRAM_LINK = {
    "name": "tl-001",
    "user": SAMPLE_USER,
    "telegram_user_id": "123456789",
    "telegram_username": "testuser",
    "first_name": "Test",
    "last_name": "User",
    "language_code": "en",
    "is_active": 1,
}


# ------------------------------------------------------------------
# Base test case with Frappe mocks
# ------------------------------------------------------------------

class ServiceTestCase(TestCase):
    """Base class for all service unit tests.

    Provides:
    - Patched ``frappe`` module (get_doc, get_all, db.exists, db.get_value, throw, commit, rollback, logger)
    - Pre-built ``self.mock_doc`` that behaves like a Frappe Document
    - Common assertion helpers
    """

    def setUp(self) -> None:
        import expense_manager.services.category_service as cat_mod
        import expense_manager.services.dependent_service as dep_mod
        import expense_manager.services.expense_service as exp_mod
        import expense_manager.services.budget_service as bud_mod
        import expense_manager.services.pocket_money_service as pm_mod
        import expense_manager.services.report_service as rpt_mod
        import expense_manager.services.telegram_link_service as tl_mod

        self._mods = {
            "category": cat_mod,
            "dependent": dep_mod,
            "expense": exp_mod,
            "budget": bud_mod,
            "pocket_money": pm_mod,
            "report": rpt_mod
,
            "telegram_link": tl_mod,
        }

        # Build a mock Document that supports attribute access
        self.mock_doc = MagicMock()
        self.mock_doc.name = "mock-doc-001"
        self.mock_doc.as_dict.return_value = {"name": "mock-doc-001"}
        self.mock_doc.owner_user = SAMPLE_USER
        self.mock_doc.guardian = SAMPLE_USER
        self.mock_doc.owner = SAMPLE_USER
        self.mock_doc.is_active = 1
        self.mock_doc.dependent = None
        self.mock_doc.category = "cat-food-001"

        # Patches applied to every service module
        self._patches: list = []
        for mod in self._mods.values():
            self._patches.extend([
                patch.object(mod.frappe, "get_doc", return_value=self.mock_doc),
                patch.object(mod.frappe, "get_all", return_value=[]),
                patch.object(mod.frappe.db, "exists", return_value=None),
                patch.object(mod.frappe.db, "get_value", return_value=None),
                patch.object(mod.frappe, "throw", side_effect=Exception("frappe.throw")),
                patch.object(mod.frappe, "commit", create=True),
                patch.object(mod.frappe, "rollback", create=True),
                patch.object(mod.frappe, "logger", return_value=MagicMock()),
            ])

        for p in self._patches:
            p.start()

        # Patch frappe.utils.today to avoid DB/Redis calls for system settings
        self._today_patch = patch.object(frappe.utils, "today", return_value="2026-07-27")
        self._today_patch.start()

        # Also patch module-local aliases of today() that won't be affected by the above
        import expense_manager.services.pocket_money_service as pm_svc
        import expense_manager.services.report_service as rpt_svc
        self._extra_today_patches = [
            patch.object(pm_svc, "frappe_today", return_value="2026-07-27"),
            patch.object(rpt_svc, "today", return_value="2026-07-27"),
        ]
        for p in self._extra_today_patches:
            p.start()

    def tearDown(self) -> None:
        for p in reversed(self._extra_today_patches):
            p.stop()
        self._today_patch.stop()
        for p in reversed(self._patches):
            p.stop()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _make_doc(self, base=None, **overrides):
        """Return a MagicMock that behaves like a Frappe Document with given field values."""
        doc = MagicMock()
        base_data = {**SAMPLE_EXPENSE, **(base or {})}
        all_data = {**base_data, **overrides}
        for key, value in all_data.items():
            setattr(doc, key, value)
        doc.as_dict.return_value = {k: getattr(doc, k) for k in dir(doc) if not k.startswith("_")}

        # Ensure common ownership fields are set when not already present
        # in the provided data, so cross-service ownership checks work.
        if "owner_user" not in all_data:
            doc.owner_user = SAMPLE_USER
        if "guardian" not in all_data:
            doc.guardian = SAMPLE_USER
        if "owner" not in all_data:
            doc.owner = SAMPLE_USER

        return doc

    def assert_raises_frappe_throw(self, callable_fn, *args, **kwargs):
        """Assert that a callable triggers frappe.throw (via the Exception mock)."""
        with self.assertRaises(Exception) as ctx:
            callable_fn(*args, **kwargs)
        self.assertIn("frappe.throw", str(ctx.exception))
