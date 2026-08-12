"""Unit tests for TelegramLinkService."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import MagicMock, PropertyMock, patch

import frappe

from expense_manager.services.exceptions import (
	ExpiredTelegramLinkCodeError,
	InvalidTelegramLinkCodeError,
	TelegramAlreadyLinkedError,
	TelegramNotLinkedError,
	TelegramUserNotFoundError,
)
from expense_manager.services.telegram_link_service import (
	LINK_TOKEN_EXPIRY_MINUTES,
	TelegramLinkService,
)
from expense_manager.tests.base import SAMPLE_TELEGRAM_LINK, SAMPLE_USER, ServiceTestCase


class TestIsLinked(ServiceTestCase):
	def test_returns_true_when_link_exists(self):
		with patch.object(frappe.db, "exists", return_value="tl-001"):
			self.assertTrue(TelegramLinkService.is_linked(SAMPLE_USER))

	def test_returns_false_when_no_link(self):
		with patch.object(frappe.db, "exists", return_value=None):
			self.assertFalse(TelegramLinkService.is_linked(SAMPLE_USER))


class TestGetUserByTelegram(ServiceTestCase):
	def test_returns_user(self):
		with patch.object(frappe.db, "get_value", return_value=SAMPLE_USER):
			result = TelegramLinkService.get_user_by_telegram("123456789")
			self.assertEqual(result, SAMPLE_USER)

	def test_raises_when_not_linked(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			with self.assertRaises(TelegramNotLinkedError):
				TelegramLinkService.get_user_by_telegram("999999999")

	def test_raises_when_empty_id(self):
		with self.assertRaises(InvalidTelegramLinkCodeError):
			TelegramLinkService.get_user_by_telegram("")

	def test_raises_when_whitespace_id(self):
		with self.assertRaises(InvalidTelegramLinkCodeError):
			TelegramLinkService.get_user_by_telegram("   ")


class TestGetLink(ServiceTestCase):
	def test_returns_doc(self):
		mock_doc = MagicMock()
		mock_doc.name = "tl-001"
		with patch.object(frappe.db, "get_value", return_value="tl-001"):
			with patch.object(frappe, "get_doc", return_value=mock_doc):
				result = TelegramLinkService.get_link(SAMPLE_USER)
				self.assertEqual(result.name, "tl-001")

	def test_raises_when_not_linked(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			with self.assertRaises(TelegramNotLinkedError):
				TelegramLinkService.get_link(SAMPLE_USER)


class TestLinkAccount(ServiceTestCase):
	@patch("expense_manager.services.telegram_link_service.TelegramLinkService.is_linked", return_value=False)
	def test_generates_token(self, _mock_linked):
		with (
			patch("expense_manager.services.telegram_link_service.frappe") as mock_frappe,
			patch(
				"expense_manager.services.telegram_link_service.now_datetime",
				return_value=datetime.now(),
			),
		):
			mock_frappe.cache.return_value = MagicMock()
			mock_frappe.db.exists.return_value = "User"
			result = TelegramLinkService.link_account(SAMPLE_USER)
			self.assertIn("token", result)
			self.assertIn("expires_at", result)
			self.assertEqual(len(result["token"]), 8)

	def test_raises_when_already_linked(self):
		with (
			patch(
				"expense_manager.services.telegram_link_service.TelegramLinkService.is_linked",
				return_value=True,
			),
			patch.object(frappe.db, "exists", return_value="User"),
		):
			with self.assertRaises(TelegramAlreadyLinkedError):
				TelegramLinkService.link_account(SAMPLE_USER)

	def test_raises_when_user_not_found(self):
		with patch(
			"expense_manager.services.telegram_link_service.TelegramLinkService.is_linked", return_value=False
		):
			with patch.object(frappe.db, "exists", return_value=None):
				with self.assertRaises(TelegramUserNotFoundError):
					TelegramLinkService.link_account("nonexistent@example.com")


class TestVerifyAndLink(ServiceTestCase):
	def test_raises_when_empty_telegram_id(self):
		with self.assertRaises(InvalidTelegramLinkCodeError):
			TelegramLinkService.verify_and_link("TOKEN1234", "")

	def test_raises_when_invalid_token(self):
		with patch("expense_manager.services.telegram_link_service.frappe") as mock_frappe:
			mock_frappe.cache.return_value = MagicMock()
			mock_frappe.cache.return_value.get_value.return_value = None
			with self.assertRaises(InvalidTelegramLinkCodeError):
				TelegramLinkService.verify_and_link("TOKEN1234", "123456789")

	def test_raises_when_token_expired(self):
		expired_payload = {
			"user": SAMPLE_USER,
			"expires_at": (datetime.now() - timedelta(minutes=5)).isoformat(),
		}
		with (
			patch("expense_manager.services.telegram_link_service.frappe") as mock_frappe,
			patch(
				"expense_manager.services.telegram_link_service.now_datetime",
				return_value=datetime.now(),
			),
		):
			mock_frappe.cache.return_value = MagicMock()
			mock_frappe.cache.return_value.get_value.return_value = expired_payload
			with self.assertRaises(ExpiredTelegramLinkCodeError):
				TelegramLinkService.verify_and_link("TOKEN1234", "123456789")

	@patch("expense_manager.services.telegram_link_service.TelegramLinkService.is_linked", return_value=True)
	def test_raises_when_already_linked_during_verify(self, _mock_linked):
		valid_payload = {
			"user": SAMPLE_USER,
			"expires_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
		}
		with (
			patch("expense_manager.services.telegram_link_service.frappe") as mock_frappe,
			patch(
				"expense_manager.services.telegram_link_service.now_datetime",
				return_value=datetime.now(),
			),
		):
			mock_frappe.cache.return_value = MagicMock()
			mock_frappe.cache.return_value.get_value.return_value = valid_payload
			with self.assertRaises(TelegramAlreadyLinkedError):
				TelegramLinkService.verify_and_link("TOKEN1234", "123456789")

	@patch("expense_manager.services.telegram_link_service.TelegramLinkService._validate_unique_link")
	@patch("expense_manager.services.telegram_link_service.TelegramLinkService.is_linked", return_value=False)
	def test_creates_doc_on_success(self, _mock_unique, _mock_linked):
		valid_payload = {
			"user": SAMPLE_USER,
			"expires_at": (datetime.now() + timedelta(minutes=5)).isoformat(),
		}
		mock_doc = MagicMock()
		mock_doc.name = "tl-new-001"

		with (
			patch("expense_manager.services.telegram_link_service.frappe") as mock_frappe,
			patch(
				"expense_manager.services.telegram_link_service.now_datetime",
				return_value=datetime.now(),
			),
		):
			mock_frappe.cache.return_value = MagicMock()
			mock_frappe.cache.return_value.get_value.return_value = valid_payload
			mock_frappe.get_doc.return_value = mock_doc

			TelegramLinkService.verify_and_link("TOKEN1234", "123456789", telegram_username="testuser")
			mock_doc.insert.assert_called_once()


class TestUnlinkAccount(ServiceTestCase):
	def test_noop_when_not_linked(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			TelegramLinkService.unlink_account(SAMPLE_USER)

	def test_deactivates_when_linked(self):
		mock_doc = MagicMock()
		mock_doc.is_active = 1
		with patch.object(frappe.db, "get_value", return_value="tl-001"):
			with patch.object(frappe, "get_doc", return_value=mock_doc):
				TelegramLinkService.unlink_account(SAMPLE_USER)
				self.assertEqual(mock_doc.is_active, 0)
				mock_doc.save.assert_called_once()


class TestListLinks(ServiceTestCase):
	def test_returns_data(self):
		with patch.object(frappe, "get_all", return_value=[SAMPLE_TELEGRAM_LINK]):
			result = TelegramLinkService.list_links()
			self.assertEqual(len(result), 1)

	def test_active_only_filter(self):
		with patch.object(frappe, "get_all", return_value=[]) as mock_get:
			TelegramLinkService.list_links(active_only=True)
			filters = mock_get.call_args[1]["filters"]
			self.assertEqual(filters["is_active"], 1)


class TestSearchLinks(ServiceTestCase):
	def test_empty_search_returns_empty(self):
		result = TelegramLinkService.search_links("")
		self.assertEqual(result, [])

	def test_none_search_returns_empty(self):
		result = TelegramLinkService.search_links(None)
		self.assertEqual(result, [])

	def test_search_by_user(self):
		with patch.object(frappe, "get_all", return_value=[SAMPLE_TELEGRAM_LINK]):
			result = TelegramLinkService.search_links("guardian")
			self.assertEqual(len(result), 1)


class TestRefreshLink(ServiceTestCase):
	def test_noop_when_not_linked(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			TelegramLinkService.refresh_link(SAMPLE_USER, telegram_username="newname")

	def test_updates_changed_fields(self):
		mock_doc = MagicMock()
		mock_doc.telegram_username = "oldname"
		mock_doc.first_name = "Old"
		mock_doc.last_name = "Name"
		mock_doc.language_code = "en"

		with patch.object(frappe.db, "get_value", return_value="tl-001"):
			with patch.object(frappe, "get_doc", return_value=mock_doc):
				TelegramLinkService.refresh_link(
					SAMPLE_USER,
					telegram_username="newname",
					first_name="New",
				)
				self.assertEqual(mock_doc.telegram_username, "newname")
				self.assertEqual(mock_doc.first_name, "New")
				mock_doc.save.assert_called_once()

	def test_no_save_when_nothing_changed(self):
		mock_doc = MagicMock()
		mock_doc.telegram_username = "same"
		mock_doc.first_name = "Same"
		mock_doc.last_name = "Name"
		mock_doc.language_code = "en"

		with patch.object(frappe.db, "get_value", return_value="tl-001"):
			with patch.object(frappe, "get_doc", return_value=mock_doc):
				TelegramLinkService.refresh_link(
					SAMPLE_USER,
					telegram_username="same",
					first_name="Same",
					last_name="Name",
					language_code="en",
				)
				mock_doc.save.assert_not_called()


class TestHashToken(ServiceTestCase):
	def test_deterministic(self):
		h1 = TelegramLinkService._hash_token("ABCDEF12")
		h2 = TelegramLinkService._hash_token("ABCDEF12")
		self.assertEqual(h1, h2)

	def test_uppercase_before_hash(self):
		h1 = TelegramLinkService._hash_token("abc")
		h2 = TelegramLinkService._hash_token("ABC")
		self.assertEqual(h1, h2)

	def test_is_sha256(self):
		h = TelegramLinkService._hash_token("TEST")
		self.assertEqual(len(h), 64)
		expected = hashlib.sha256(b"TEST").hexdigest()
		self.assertEqual(h, expected)


class TestValidateUniqueLink(ServiceTestCase):
	def test_raises_when_conflicting_user(self):
		with patch.object(frappe.db, "get_value", return_value="other@example.com"):
			with self.assertRaises(TelegramAlreadyLinkedError):
				TelegramLinkService._validate_unique_link(SAMPLE_USER, "123456789")

	def test_passes_when_same_user(self):
		with patch.object(frappe.db, "get_value", return_value=SAMPLE_USER):
			TelegramLinkService._validate_unique_link(SAMPLE_USER, "123456789")

	def test_passes_when_no_conflict(self):
		with patch.object(frappe.db, "get_value", return_value=None):
			TelegramLinkService._validate_unique_link(SAMPLE_USER, "123456789")
