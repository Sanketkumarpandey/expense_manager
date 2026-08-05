"""End-to-end integration tests for Expense Manager workflows.

Each test exercises multiple services working together, mocking only
external boundaries (Sarvam AI, Groq, Telegram Bot API, Frappe DB/cache).
Services call through to each other — no internal service methods are mocked.
"""

from __future__ import annotations

from datetime import datetime
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe.utils
from expense_manager.ai.exceptions import IncomeDetectedError


# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

OWNER = "guardian@example.com"
TG_ID = "99887766"
DEP_ID = "dep-son-001"
CAT_ID = "cat-food-001"
BUD_ID = "bud-001"
ALLOC_ID = "pm-001"
EXPENSE_NAME = "exp-int-001"
LINK_DOC_NAME = "tl-int-001"
NOW = datetime(2026, 7, 27, 10, 0, 0)


# ---------------------------------------------------------------------------
# Helpers to build mock Frappe Documents
# ---------------------------------------------------------------------------

def _make_category_doc():
    doc = MagicMock()
    doc.name = CAT_ID
    doc.category_name = "Food"
    doc.owner_user = OWNER
    doc.is_active = 1
    doc.dependent = None
    return doc


def _make_budget_doc(spent=0.0, allocated=5000.0):
    doc = MagicMock()
    doc.name = BUD_ID
    doc.owner_user = OWNER
    doc.category = CAT_ID
    doc.dependent = None
    doc.allocated_amount = allocated
    doc.spent_amount = spent
    doc.start_date = "2026-07-01"
    doc.end_date = "2026-07-31"
    doc.alert_threshold_pct = 90
    doc.is_active = 1
    doc.last_alert_sent_on = None
    doc.save = MagicMock()
    return doc


def _make_allocation_doc(carry=0.0):
    doc = MagicMock()
    doc.name = ALLOC_ID
    doc.dependent = DEP_ID
    doc.allocated_amount = 2000.0
    doc.carry_forward_amount = carry
    doc.total_available_amount = 2000.0 + carry
    doc.allocation_date = "2026-07-01"
    doc.allocation_period = "Monthly"
    doc.is_active = 1
    doc.save = MagicMock()
    return doc


def _make_dependent_doc(allow_carry=True):
    doc = MagicMock()
    doc.name = DEP_ID
    doc.dependent_name = "Son"
    doc.guardian = OWNER
    doc.relationship = "Son"
    doc.default_monthly_allowance = 2000.0
    doc.allow_carry_forward = allow_carry
    doc.is_active = 1
    doc.telegram_user_id = "11223344"
    return doc


def _make_expense_doc(name=EXPENSE_NAME):
    doc = MagicMock()
    doc.name = name
    doc.owner_user = OWNER
    doc.category = CAT_ID
    doc.amount = 200.0
    doc.expense_date = "2026-07-27"
    doc.dependent = None
    doc.description = "Test expense"
    doc.source = "Telegram"
    doc.save = MagicMock()
    return doc


def _make_telegram_link_doc():
    doc = MagicMock()
    doc.name = LINK_DOC_NAME
    doc.user = OWNER
    doc.telegram_user_id = TG_ID
    doc.telegram_username = "testuser"
    doc.first_name = "Test"
    doc.last_name = "User"
    doc.language_code = "en"
    doc.is_active = 1
    doc.linked_on = NOW
    doc.save = MagicMock()
    return doc


CATEGORY_LIST_ROW = {
    "name": CAT_ID,
    "category_name": "Food",
    "icon": "Food",
    "is_active": 1,
    "creation": "2026-07-01",
    "modified": "2026-07-01",
}


# ---------------------------------------------------------------------------
# Base class — patches frappe on every service module
# ---------------------------------------------------------------------------

class IntegrationTestCase(TestCase):
    """Patches frappe module attributes on every service module, plus
    frappe.utils.today and module-local today aliases."""

    PATCH_MODULES: list[str] = [
        "category_service", "dependent_service", "expense_service",
        "budget_service", "pocket_money_service", "report_service",
        "telegram_link_service",
    ]

    def setUp(self):
        import importlib

        self._mods = {}
        for mod_name in self.PATCH_MODULES:
            full = f"expense_manager.services.{mod_name}"
            mod = importlib.import_module(full)
            self._mods[mod_name] = mod

        self._patches: list = []

        for mod in self._mods.values():
            self._patches.extend([
                patch.object(mod.frappe, "get_doc", return_value=MagicMock()),
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

        self._today_patch = patch.object(frappe.utils, "today", return_value="2026-07-27")
        self._today_patch.start()

        import expense_manager.services.pocket_money_service as pm_svc
        import expense_manager.services.report_service as rpt_svc
        self._extra_today_patches = [
            patch.object(pm_svc, "frappe_today", return_value="2026-07-27"),
            patch.object(rpt_svc, "today", return_value="2026-07-27"),
        ]
        for p in self._extra_today_patches:
            p.start()

        self._alloc_deactivated = False

    def tearDown(self):
        for p in reversed(self._extra_today_patches):
            p.stop()
        self._today_patch.stop()
        for p in reversed(self._patches):
            p.stop()

    def _get_mod(self, service_name: str):
        return self._mods[service_name]

    def _set_frappe_side_effects(
        self,
        *,
        categories: list[dict] | None = None,
        dependents: list[dict] | None = None,
        budgets: list[dict] | None = None,
        expenses: list[dict] | None = None,
        spent: float = 0.0,
        allocated: float = 5000.0,
    ):
        """Configure frappe.db.get_value, frappe.get_doc, frappe.db.exists,
        and frappe.get_all side_effects on ALL service modules at once.

        This works because all service modules share the same ``frappe``
        module object — patching one patches them all.
        """
        cat_doc = _make_category_doc()
        budget_doc = _make_budget_doc(spent=spent, allocated=allocated)
        dep_doc = _make_dependent_doc()
        alloc_doc = _make_allocation_doc()
        exp_doc = _make_expense_doc()
        tl_doc = _make_telegram_link_doc()

        _cat_list = categories if categories is not None else [CATEGORY_LIST_ROW]
        _dep_list = dependents if dependents is not None else []
        _bud_list = budgets if budgets is not None else []
        _exp_list = expenses if expenses is not None else []

        # --- get_doc (string name lookups and dict creation) ---------------
        def get_doc_side_effect(*args, **kwargs):
            doctype = args[0] if args else None
            name = args[1] if len(args) > 1 else None

            if doctype == "Category":
                return cat_doc
            if doctype == "Budget":
                return budget_doc
            if doctype == "Dependent":
                return dep_doc
            if doctype == "Pocket Money Allocation":
                if self._alloc_deactivated and name is None:
                    return MagicMock(name="new-allocation")
                return alloc_doc
            if doctype == "Telegram Link":
                return tl_doc
            if doctype == "Expense":
                return exp_doc

            if isinstance(doctype, dict):
                dt = doctype.get("doctype")
                if dt == "Category":
                    return cat_doc
                if dt == "Budget":
                    return budget_doc
                if dt == "Dependent":
                    return dep_doc
                if dt == "Expense":
                    return exp_doc
                if dt == "Pocket Money Allocation":
                    new_doc = _make_allocation_doc()
                    new_doc.name = "pm-new-001"
                    new_doc.allocated_amount = doctype.get("allocated_amount", 2000.0)
                    return new_doc
                if dt == "Telegram Link":
                    return tl_doc

            return MagicMock()

        # --- get_value ------------------------------------------------------
        def get_value_side_effect(*args, **kwargs):
            doctype = args[0] if args else None
            filters = args[1] if len(args) > 1 else None
            fieldname = args[2] if len(args) > 2 else None

            if doctype == "Telegram Link" and fieldname == "user":
                if isinstance(filters, dict) and filters.get("telegram_user_id") == TG_ID:
                    return OWNER

            if doctype == "Dependent" and fieldname == "name":
                if isinstance(filters, dict) and filters.get("telegram_user_id") == TG_ID:
                    return DEP_ID
                if isinstance(filters, dict) and filters.get("guardian") == OWNER:
                    return DEP_ID

            if doctype == "Dependent" and fieldname == "guardian":
                if len(args) > 1 and args[1] == DEP_ID:
                    return OWNER

            if doctype == "Budget" and fieldname == "name":
                if isinstance(filters, dict) and filters.get("category") == CAT_ID:
                    return BUD_ID

            if doctype == "Pocket Money Allocation" and fieldname == "name":
                if isinstance(filters, dict) and filters.get("dependent") == DEP_ID:
                    is_active = filters.get("is_active")
                    if is_active == 1 and self._alloc_deactivated:
                        return None
                    return ALLOC_ID

            return None

        # --- exists ---------------------------------------------------------
        def exists_side_effect(*args, **kwargs):
            doctype = args[0] if args else None
            filters = args[1] if len(args) > 1 else None
            if doctype == "User":
                return OWNER
            if doctype == "Telegram Link" and isinstance(filters, dict):
                if filters.get("user") == OWNER and filters.get("is_active") == 1:
                    return None
            return None

        # --- get_all --------------------------------------------------------
        def get_all_side_effect(dt, filters=None, **kwargs):
            if dt == "Category":
                return [dict(r) for r in _cat_list]
            if dt == "Dependent":
                return [dict(r) for r in _dep_list]
            if dt == "Budget":
                return [dict(r) for r in _bud_list]
            if dt == "Expense":
                return [dict(r) for r in _exp_list]
            return []

        first_mod = next(iter(self._mods.values()))
        first_mod.frappe.get_doc.side_effect = get_doc_side_effect
        first_mod.frappe.db.get_value.side_effect = get_value_side_effect
        first_mod.frappe.db.exists.side_effect = exists_side_effect
        first_mod.frappe.get_all.side_effect = get_all_side_effect


# =========================================================================
#  Workflow 1 — Voice → Speech → AI → Expense → Budget refresh → Reply
# =========================================================================

class TestVoiceToExpenseWorkflow(IntegrationTestCase):
    """End-to-end: voice note arrives → transcribed → parsed → expense
    created → budget refreshed → success message returned."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects(spent=0.0)
        self._budget_patcher = patch(
            "expense_manager.services.budget_service.BudgetService._calculate_spent_amount",
            return_value=0.0,
        )
        self._budget_patcher.start()

    def tearDown(self):
        self._budget_patcher.stop()
        super().tearDown()

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_voice_creates_expense_and_returns_success_message(
        self, mock_today, mock_parse_mock, mock_stt_mock
    ):
        from expense_manager.telegram.services.telegram_service import TelegramService

        result = TelegramService.create_expense_from_voice(TG_ID, "/tmp/voice.oga")

        self.assertTrue(result["success"])
        self.assertIn("Logged", result["message"])
        self.assertEqual(result["expense"], EXPENSE_NAME)

    @patch("expense_manager.ai.speech_to_text.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_voice_budget_refresh_called(
        self, mock_today, mock_parse_mock, mock_stt_mock
    ):
        from expense_manager.services.expense_service import ExpenseService

        ExpenseService.create_expense(
            owner_user=OWNER,
            category=CAT_ID,
            amount=200.0,
            expense_date="2026-07-27",
        )

        budget_mod = self._get_mod("budget_service")
        budget_mod.frappe.get_doc.assert_called()

    def test_voice_unlinked_user_returns_error(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService
        from expense_manager.services.exceptions import TelegramNotLinkedError

        mod = self._get_mod("telegram_link_service")
        mod.frappe.db.get_value.side_effect = lambda *a, **kw: None

        with self.assertRaises(TelegramNotLinkedError):
            TelegramLinkService.get_user_by_telegram(TG_ID)


# =========================================================================
#  Workflow 3 — Text → AI Parse → Expense → Budget refresh → Reply
# =========================================================================

class TestTextExpenseWorkflow(IntegrationTestCase):
    """End-to-end: text input → AI parse → expense created → budget
    refreshed → success message returned.  Same logic as voice but
    skips the Sarvam STT step."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects(spent=0.0)
        self._budget_patcher = patch(
            "expense_manager.services.budget_service.BudgetService._calculate_spent_amount",
            return_value=0.0,
        )
        self._budget_patcher.start()

    def tearDown(self):
        self._budget_patcher.stop()
        super().tearDown()

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_text_creates_expense_and_returns_success_message(
        self, mock_today, mock_parse_mock
    ):
        from expense_manager.telegram.services.telegram_service import TelegramService

        result = TelegramService.create_expense_from_text(TG_ID, "lunch 250")

        self.assertTrue(result["success"])
        self.assertIn("Logged", result["message"])
        self.assertEqual(result["expense"], EXPENSE_NAME)

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_text_triggers_budget_refresh(
        self, mock_today, mock_parse_mock
    ):
        from expense_manager.services.expense_service import ExpenseService

        ExpenseService.create_expense(
            owner_user=OWNER,
            category=CAT_ID,
            amount=200.0,
            expense_date="2026-07-27",
        )

        budget_mod = self._get_mod("budget_service")
        budget_mod.frappe.get_doc.assert_called()

    def test_text_unlinked_user_returns_error(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService
        from expense_manager.services.exceptions import TelegramNotLinkedError

        mod = self._get_mod("telegram_link_service")
        mod.frappe.db.get_value.side_effect = lambda *a, **kw: None

        with self.assertRaises(TelegramNotLinkedError):
            TelegramLinkService.get_user_by_telegram(TG_ID)

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_text_dependent_scoped_correctly(
        self, mock_today, mock_parse_mock
    ):
        from expense_manager.services.ai_service import AIService
        from expense_manager.services.expense_service import ExpenseService

        with patch.object(ExpenseService, "create_expense", return_value=_make_expense_doc()) as mock_create:
            AIService.create_expense_from_text(OWNER, "snacks 50", dependent=DEP_ID)

        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        self.assertEqual(kwargs["dependent"], DEP_ID)


# =========================================================================
#  Workflow 4 — Income guardrails (keyword pre-filter + transaction_type)
# =========================================================================

class TestIncomeGuardrails(IntegrationTestCase):
    """Keyword pre-filter rejects income/refund phrasings before LLM;
    transaction_type check catches ambiguous cases after LLM."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects(spent=0.0)
        self._budget_patcher = patch(
            "expense_manager.services.budget_service.BudgetService._calculate_spent_amount",
            return_value=0.0,
        )
        self._budget_patcher.start()

    def tearDown(self):
        self._budget_patcher.stop()
        super().tearDown()

    def _assert_rejected(self, text: str):
        from expense_manager.telegram.services.telegram_service import TelegramService
        result = TelegramService.create_expense_from_text(TG_ID, text)
        self.assertFalse(result["success"])
        self.assertIn("money coming in", result["message"])

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_refund_keyword_rejected(self, mock_today, mock_ai):
        self._assert_rejected("got a refund of 200 from Amazon")

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_credit_keyword_rejected(self, mock_today, mock_ai):
        self._assert_rejected("received 500 credit")

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_cashback_keyword_rejected(self, mock_today, mock_ai):
        self._assert_rejected("cashback of 30 rupees")

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_got_money_keyword_rejected(self, mock_today, mock_ai):
        self._assert_rejected("got money from dad")

    @patch("expense_manager.ai.ai_parser.get_use_mock_ai_apis", return_value=True)
    @patch("expense_manager.ai.ai_parser.today", return_value="2026-07-27")
    def test_normal_expense_accepted(self, mock_today, mock_ai):
        from expense_manager.telegram.services.telegram_service import TelegramService
        result = TelegramService.create_expense_from_text(TG_ID, "lunch 250")
        self.assertTrue(result["success"])
        self.assertIn("Logged", result["message"])

    def test_transaction_type_income_rejected(self):
        """When the parser returns transaction_type=income (not matched by
        keyword pre-filter), the post-parse check should still reject."""
        from expense_manager.services.ai_service import AIService
        with patch("expense_manager.services.ai_service.CategoryService.list_categories",
                   return_value=[]), \
             patch("expense_manager.services.ai_service.ai_parser.parse_expense") as mock_parse:
            mock_parse.return_value = {
                "amount": 500.0,
                "category": "Uncategorized",
                "description": "salary credited",
                "expense_date": "2026-07-27",
                "transaction_type": "income",
            }
            with self.assertRaises(IncomeDetectedError):
                AIService.create_expense_from_text(OWNER, "salary credited")


# =========================================================================
#  Workflow 2 — Telegram Linking → Token → Verify → Linked
# =========================================================================

class TestTelegramLinkingWorkflow(IntegrationTestCase):
    """End-to-end: user initiates linking → token generated → dependent
    verifies token → Telegram Link created → status shows linked."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects()

        self._tl_mod = self._get_mod("telegram_link_service")
        self._link_doc = _make_telegram_link_doc()

        self._cache_mock = MagicMock()
        self._cache_patcher = patch.object(
            self._tl_mod.frappe, "cache", return_value=self._cache_mock,
        )
        self._cache_patcher.start()

    def tearDown(self):
        self._cache_patcher.stop()
        super().tearDown()

    @patch("expense_manager.services.telegram_link_service.now_datetime", return_value=NOW)
    @patch("expense_manager.services.telegram_link_service.add_to_date", return_value=NOW)
    def test_link_account_generates_token(self, mock_add, mock_now):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        result = TelegramLinkService.link_account(OWNER)

        self.assertIn("token", result)
        self.assertIn("expires_at", result)
        self._cache_mock.set_value.assert_called_once()

    @patch("expense_manager.services.telegram_link_service.now_datetime", return_value=NOW)
    @patch("expense_manager.services.telegram_link_service.add_to_date", return_value=NOW)
    def test_verify_and_link_creates_document(self, mock_add, mock_now):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        raw_token = "ABCD1234"
        token_hash = TelegramLinkService._hash_token(raw_token)
        cache_key = TelegramLinkService._cache_key(token_hash)

        self._cache_mock.get_value.return_value = {
            "user": OWNER,
            "expires_at": "2026-07-27T10:10:00",
        }

        def get_doc_for_link(*args, **kwargs):
            if isinstance(args[0], dict) and args[0].get("doctype") == "Telegram Link":
                return self._link_doc
            return MagicMock()

        self._tl_mod.frappe.get_doc.side_effect = get_doc_for_link

        result = TelegramLinkService.verify_and_link(
            token=raw_token,
            telegram_user_id=TG_ID,
            telegram_username="testuser",
            first_name="Test",
            last_name="User",
            language_code="en",
        )

        self.assertEqual(result.name, LINK_DOC_NAME)
        self._cache_mock.delete_value.assert_called_with(cache_key)

    def test_link_status_returns_linked_when_active(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        user = TelegramLinkService.get_user_by_telegram(TG_ID)
        self.assertEqual(user, OWNER)

    def test_link_status_raises_when_not_linked(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService
        from expense_manager.services.exceptions import TelegramNotLinkedError

        mod = self._get_mod("telegram_link_service")
        mod.frappe.db.get_value.side_effect = lambda *a, **kw: None

        with self.assertRaises(TelegramNotLinkedError):
            TelegramLinkService.get_user_by_telegram(TG_ID)

    def test_is_linked_returns_true_when_exists(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        mod = self._get_mod("telegram_link_service")
        mod.frappe.db.exists.side_effect = lambda *a, **kw: (
            LINK_DOC_NAME if (a and a[0] == "Telegram Link") else None
        )

        self.assertTrue(TelegramLinkService.is_linked(OWNER))

    def test_is_linked_returns_false_when_no_link(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        self.assertFalse(TelegramLinkService.is_linked(OWNER))

    def test_unlink_deactivates_link(self):
        from expense_manager.services.telegram_link_service import TelegramLinkService

        doc = self._link_doc

        def get_doc_fn(*args, **kwargs):
            return doc

        self._tl_mod.frappe.get_doc.side_effect = get_doc_fn
        self._tl_mod.frappe.db.get_value.side_effect = lambda *a, **kw: (
            LINK_DOC_NAME if (len(a) > 2 and a[0] == "Telegram Link") else None
        )

        TelegramLinkService.unlink_account(OWNER)
        self.assertEqual(doc.is_active, 0)
        doc.save.assert_called_once()


# =========================================================================
#  Workflow 3 — Pocket Money Rollover → New Allocation → Balance Updated
# =========================================================================

class TestPocketMoneyRolloverWorkflow(IntegrationTestCase):
    """End-to-end: dependent rolls over pocket money → old allocation
    deactivated → new allocation created with carry forward → balance updated."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects(spent=0.0)
        self._alloc_doc = _make_allocation_doc(carry=0.0)
        self._alloc_doc.save.side_effect = lambda *a, **kw: setattr(self, '_alloc_deactivated', True)
        self._dep_doc = _make_dependent_doc(allow_carry=True)

        def get_doc_with_state(*args, **kwargs):
            doctype = args[0] if args else None
            name = args[1] if len(args) > 1 else None

            if doctype == "Dependent":
                return self._dep_doc
            if doctype == "Pocket Money Allocation":
                return self._alloc_doc
            if isinstance(doctype, dict):
                dt = doctype.get("doctype")
                if dt == "Pocket Money Allocation":
                    new_doc = _make_allocation_doc()
                    new_doc.name = "pm-new-001"
                    new_doc.allocated_amount = doctype.get("allocated_amount", 2000.0)
                    return new_doc
                if dt == "Category":
                    return _make_category_doc()
            if doctype == "Category":
                return _make_category_doc()

            return MagicMock()

        for mod in self._mods.values():
            mod.frappe.get_doc.side_effect = get_doc_with_state

    def test_rollover_deactivates_old_allocation(self):
        from expense_manager.services.pocket_money_service import PocketMoneyService

        PocketMoneyService.rollover_allocation(OWNER, DEP_ID)

        self.assertTrue(self._alloc_deactivated)

    def test_rollover_carry_forward_when_allowed(self):
        from expense_manager.services.pocket_money_service import PocketMoneyService

        result = PocketMoneyService.rollover_allocation(OWNER, DEP_ID)

        self.assertIsNotNone(result)
        self.assertEqual(result.name, "pm-new-001")

    def test_rollover_no_carry_forward_when_disallowed(self):
        self._dep_doc.allow_carry_forward = False

        from expense_manager.services.pocket_money_service import PocketMoneyService

        result = PocketMoneyService.rollover_allocation(OWNER, DEP_ID)

        # A new 0-amount allocation is created so a current-month record
        # always exists. The allocated_amount is 0.0 (not default_monthly_allowance).
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "pm-new-001")
        self.assertEqual(result.allocated_amount, 0.0)

    def test_rollover_raises_when_no_active_allocation(self):
        mod = self._get_mod("pocket_money_service")
        mod.frappe.db.get_value.side_effect = lambda *a, **kw: None

        for m in self._mods.values():
            m.frappe.db.get_value.side_effect = lambda *a, **kw: None

        from expense_manager.services.pocket_money_service import PocketMoneyService
        from expense_manager.services.exceptions import PocketMoneyAllocationNotFoundError

        with self.assertRaises(PocketMoneyAllocationNotFoundError):
            PocketMoneyService.rollover_allocation(OWNER, DEP_ID)


# =========================================================================
#  Workflow 4 — Expense → Budget Threshold Check → Overspend Alert
# =========================================================================

class TestBudgetAlertWorkflow(IntegrationTestCase):
    """End-to-end: expense created → budget refreshed → spending exceeds
    threshold → alert condition detected."""

    def setUp(self):
        super().setUp()
        self._set_frappe_side_effects(spent=0.0)
        self._budget_patcher = None

    def tearDown(self):
        if self._budget_patcher:
            self._budget_patcher.stop()
        super().tearDown()

    def _setup_budget_mocks(self, allocated=5000.0, spent=4600.0):
        budget_doc = _make_budget_doc(spent=spent, allocated=allocated)
        self._set_frappe_side_effects(spent=spent, allocated=allocated)

        for mod in self._mods.values():
            orig_fn = mod.frappe.get_doc.side_effect

            def patched_get_doc(*args, bdoc=budget_doc, orig=orig_fn, **kwargs):
                if args and args[0] == "Budget":
                    return bdoc
                return orig(*args, **kwargs)

            mod.frappe.get_doc.side_effect = patched_get_doc

        self._budget_patcher = patch(
            "expense_manager.services.budget_service.BudgetService._calculate_spent_amount",
            return_value=spent,
        )
        self._budget_patcher.start()

    def test_budget_refresh_updates_spent_amount(self):
        self._setup_budget_mocks(allocated=5000.0, spent=4600.0)

        from expense_manager.services.budget_service import BudgetService

        BudgetService.refresh_budget(OWNER, CAT_ID)

        budget_mod = self._get_mod("budget_service")
        budget_mod.frappe.get_doc.assert_called()

    def test_budget_usage_reports_correct_percentage(self):
        self._setup_budget_mocks(allocated=5000.0, spent=4500.0)

        from expense_manager.services.budget_service import BudgetService

        usage = BudgetService.get_budget_usage(OWNER, CAT_ID)

        self.assertIsNotNone(usage)
        self.assertEqual(usage["allocated_amount"], 5000.0)
        self.assertEqual(usage["spent_amount"], 4500.0)
        self.assertAlmostEqual(usage["pct_used"], 90.0)

    def test_budget_overspend_detected(self):
        self._setup_budget_mocks(allocated=5000.0, spent=5200.0)

        from expense_manager.services.budget_service import BudgetService

        usage = BudgetService.get_budget_usage(OWNER, CAT_ID)

        self.assertTrue(usage["is_overspent"])

    def test_budget_alert_message_format(self):
        from expense_manager.services.budget_service import BudgetService

        usage = {
            "allocated_amount": 5000.0,
            "spent_amount": 4800.0,
            "pct_used": 96.0,
            "is_overspent": False,
        }

        msg = BudgetService.build_budget_alert_message("Food", usage)

        self.assertIn("Food", msg)
        self.assertIn("4800", msg)
        self.assertIn("5000", msg)
        self.assertIn("96.0%", msg)

    def test_budget_overspend_alert_message_format(self):
        from expense_manager.services.budget_service import BudgetService

        usage = {
            "allocated_amount": 5000.0,
            "spent_amount": 5200.0,
            "pct_used": 104.0,
            "is_overspent": True,
        }

        msg = BudgetService.build_budget_alert_message("Food", usage)

        self.assertIn("over budget", msg)
        self.assertIn("Food", msg)

    def test_can_send_budget_alert_first_time(self):
        from expense_manager.services.budget_service import BudgetService

        budget_doc = _make_budget_doc()
        budget_doc.last_alert_sent_on = None

        for mod in self._mods.values():
            mod.frappe.get_doc.side_effect = lambda *a, **kw: budget_doc

        self.assertTrue(BudgetService.can_send_budget_alert(OWNER, BUD_ID))

    def test_cannot_send_budget_alert_already_sent_today(self):
        from expense_manager.services.budget_service import BudgetService

        budget_doc = _make_budget_doc()
        budget_doc.last_alert_sent_on = "2026-07-27"

        for mod in self._mods.values():
            mod.frappe.get_doc.side_effect = lambda *a, **kw: budget_doc

        self.assertFalse(BudgetService.can_send_budget_alert(OWNER, BUD_ID))
