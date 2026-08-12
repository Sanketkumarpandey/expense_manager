"""Tests for ``api/users.py`` — ``register_guardian``.

Two layers:

- **Mocked unit tests** (``unittest.TestCase``): the admin guard, email /
  first_name validation, and the create / idempotent paths with ``frappe``
  mocked out.
- **Real-DB integration tests** (``frappe.tests.IntegrationTestCase``): the
  endpoint actually provisions a User + Has Role + 13 Category rows against
  the live ``expense.local`` database. This is the first genuine real-DB
  test category in this repo. Every write is undone by a per-test
  ``frappe.db.rollback()`` and the session user is pinned back to
  Administrator in ``tearDown`` regardless of outcome.
"""

import secrets
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from expense_manager.api import users as api_users
from expense_manager.constants.default_categories import DEFAULT_CATEGORIES
from expense_manager.constants.roles import GUARDIAN_ROLE


def _unique_email(prefix: str) -> str:
	return f"{prefix}-{secrets.token_hex(4)}@example.com"


# =========================================================================
# Mocked unit tests
# =========================================================================


class TestRegisterGuardianMocked(TestCase):
	"""Guard, validation and provisioning logic with ``frappe`` mocked."""

	def setUp(self) -> None:
		self._patches: list = []

	def tearDown(self) -> None:
		for p in reversed(self._patches):
			p.stop()

	def _patch_session(self, user: str, roles: list[str]) -> None:
		"""Pin ``frappe.session.user`` and ``frappe.get_roles`` for a test."""
		self._patches.append(patch.object(api_users.frappe, "session", SimpleNamespace(user=user)))
		self._patches.append(patch.object(api_users.frappe, "get_roles", return_value=roles))
		for p in self._patches[-2:]:
			p.start()

	def _provision_patches(self):
		"""Common mocks for the provisioning paths (get_doc/db.exists/CategoryService).

		Returns (mock_get_doc, mock_cat) where ``mock_cat`` is the mocked
		``CategoryService`` class attribute.
		"""
		mock_get_doc = MagicMock()
		patchers = [
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists", return_value=None),
			patch.object(api_users, "CategoryService"),
		]
		for p in patchers:
			p.start()
		self._patches.extend(patchers)
		return mock_get_doc, api_users.CategoryService

	# -- (a) System Manager caller -------------------------------------------

	def test_system_manager_creates_user_with_role_and_seeds(self):
		self._patch_session("sysadmin@example.com", ["System Manager"])
		mock_get_doc, mock_cat = self._provision_patches()
		doc = MagicMock()
		doc.insert.return_value = doc
		# get_doc dict call needs to return the fresh doc for .insert()
		mock_get_doc.side_effect = lambda *a, **kw: doc

		result = api_users.register_guardian(" Guardian@Example.com ", "Guardian", send_welcome_email=False)

		self.assertEqual(result, {"success": True, "user": "guardian@example.com", "created": True})
		user_dict = mock_get_doc.call_args[0][0]
		self.assertEqual(user_dict["doctype"], "User")
		self.assertEqual(user_dict["email"], "guardian@example.com")
		self.assertEqual(user_dict["roles"], [{"role": GUARDIAN_ROLE}])
		self.assertFalse(user_dict["send_welcome_email"])
		doc.insert.assert_called_once_with(ignore_permissions=True)
		mock_cat.create_default_categories.assert_called_once_with("guardian@example.com")

	# -- (b) Expense Manager User caller -------------------------------------

	def test_expense_manager_user_rejected(self):
		self._patch_session("guardian@example.com", ["Expense Manager User"])
		mock_get_doc = MagicMock()
		with (
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists") as mock_exists,
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			with self.assertRaises(frappe.PermissionError):
				api_users.register_guardian("victim@example.com", "Victim")

		mock_get_doc.assert_not_called()
		mock_exists.assert_not_called()
		mock_cat.create_default_categories.assert_not_called()

	# -- (c) Guest caller ----------------------------------------------------

	def test_guest_rejected(self):
		self._patch_session("Guest", ["Guest"])
		mock_get_doc = MagicMock()
		with (
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists") as mock_exists,
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			with self.assertRaises(frappe.PermissionError):
				api_users.register_guardian("victim@example.com", "Victim")

		mock_get_doc.assert_not_called()
		mock_exists.assert_not_called()
		mock_cat.create_default_categories.assert_not_called()

	# -- (d) Existing user → idempotent path --------------------------------

	def test_existing_user_role_ensured_when_missing(self):
		user_doc = MagicMock()
		user_doc.add_roles = MagicMock()

		def _get_doc(doctype_or_dict, name=None, **kwargs):
			if doctype_or_dict == "User" and name == "guardian@example.com":
				return user_doc
			return None

		self._patch_session("Administrator", ["Administrator", "System Manager"])
		with (
			patch.object(api_users.frappe, "get_doc", side_effect=_get_doc) as mock_get_doc,
			patch.object(api_users.frappe.db, "exists", return_value="guardian@example.com"),
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			result = api_users.register_guardian("guardian@example.com", "Guardian")

		self.assertEqual(result, {"success": True, "user": "guardian@example.com", "created": False})
		user_doc.add_roles.assert_called_once_with(GUARDIAN_ROLE)
		mock_cat.create_default_categories.assert_called_once_with("guardian@example.com")
		# the user was fetched, not re-inserted
		mock_get_doc.assert_called_once_with("User", "guardian@example.com")

	def test_existing_user_role_already_present_is_noop(self):
		user_doc = MagicMock()
		user_doc.add_roles = MagicMock()

		def _get_doc(doctype_or_dict, name=None, **kwargs):
			return user_doc if (doctype_or_dict == "User" and name == "guardian@example.com") else None

		# get_roles(email) already includes the guardian role → no add_roles call
		self._patches.append(patch.object(api_users.frappe, "session", SimpleNamespace(user="Administrator")))
		self._patches.append(patch.object(api_users.frappe, "get_roles", return_value=[GUARDIAN_ROLE]))
		for p in self._patches[-2:]:
			p.start()
		with (
			patch.object(api_users.frappe, "get_doc", side_effect=_get_doc) as mock_get_doc,
			patch.object(api_users.frappe.db, "exists", return_value="guardian@example.com"),
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			result = api_users.register_guardian("guardian@example.com", "Guardian")

		self.assertEqual(result, {"success": True, "user": "guardian@example.com", "created": False})
		user_doc.add_roles.assert_not_called()
		mock_cat.create_default_categories.assert_called_once_with("guardian@example.com")
		mock_get_doc.assert_called_once_with("User", "guardian@example.com")

	# -- (e) Invalid / missing input ----------------------------------------

	def test_invalid_email_rejected_before_provisioning(self):
		self._patch_session("Administrator", ["Administrator", "System Manager"])
		mock_get_doc = MagicMock()
		with (
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists") as mock_exists,
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			with self.assertRaises(frappe.InvalidEmailAddressError):
				api_users.register_guardian("not-an-email", "Test")

		mock_get_doc.assert_not_called()
		mock_exists.assert_not_called()
		mock_cat.create_default_categories.assert_not_called()

	def test_missing_email_rejected_before_provisioning(self):
		self._patch_session("Administrator", ["Administrator"])
		mock_get_doc = MagicMock()
		with (
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists") as mock_exists,
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			with self.assertRaises(frappe.ValidationError):
				api_users.register_guardian("", "Test")

		mock_get_doc.assert_not_called()
		mock_exists.assert_not_called()
		mock_cat.create_default_categories.assert_not_called()

	def test_missing_first_name_rejected_before_provisioning(self):
		self._patch_session("Administrator", ["Administrator"])
		mock_get_doc = MagicMock()
		with (
			patch.object(api_users.frappe, "get_doc", mock_get_doc),
			patch.object(api_users.frappe.db, "exists") as mock_exists,
			patch.object(api_users, "CategoryService") as mock_cat,
		):
			with self.assertRaises(frappe.ValidationError):
				api_users.register_guardian("guardian@example.com", "")

		mock_get_doc.assert_not_called()
		mock_exists.assert_not_called()
		mock_cat.create_default_categories.assert_not_called()


# =========================================================================
# Real-DB integration tests
# =========================================================================


class TestRegisterGuardianOnLiveDb(frappe.tests.IntegrationTestCase):
	"""Real-DB: register_guardian against the live site.

	Each test runs as Administrator, provisions role/category data via the
	real ORM, asserts against the real database, then rolls the transaction
	back so no Has Role / Category / User rows survive. The session user is
	restored to Administrator in tearDown regardless of test outcome.
	"""

	def setUp(self) -> None:
		super().setUp()
		frappe.set_user("Administrator")

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		super().tearDown()

	def test_administrator_provisions_guardian_with_role_and_categories(self):
		email = _unique_email("guard")

		result = api_users.register_guardian(email, "Integration Guardian", send_welcome_email=False)

		self.assertTrue(result["success"])
		self.assertTrue(result["created"])
		self.assertEqual(result["user"], email)

		self.assertTrue(frappe.db.exists("User", email))
		# Assert against the DB directly, not the request-local roles cache.
		self.assertTrue(frappe.db.exists("Has Role", {"parent": email, "role": GUARDIAN_ROLE}))
		role_rows = frappe.get_all(
			"Has Role", filters={"parent": email, "role": GUARDIAN_ROLE}, fields=["name"]
		)
		self.assertEqual(len(role_rows), 1)

		# Exactly the default set — the user_on_update hook and the explicit
		# call both run, but create_default_categories is idempotent.
		category_rows = frappe.get_all(
			"Category", filters={"owner_user": email, "is_active": 1}, fields=["name"]
		)
		self.assertEqual(len(category_rows), len(DEFAULT_CATEGORIES))
		self.assertEqual(len(category_rows), 13)

	def test_real_permission_check_rejects_role_less_user(self):
		roleless = _unique_email("roleless")
		frappe.get_doc({"doctype": "User", "email": roleless, "first_name": "Roleless"}).insert(
			ignore_permissions=True
		)
		self.addCleanup(frappe.set_user, "Administrator")

		victim = _unique_email("victim")
		frappe.set_user(roleless)
		try:
			with self.assertRaises(frappe.PermissionError):
				api_users.register_guardian(victim, "Victim")
		finally:
			frappe.set_user("Administrator")

		# The guard ran before any provisioning — nothing was created.
		self.assertFalse(frappe.db.exists("User", victim))

	def test_plain_desktop_creation_is_not_a_blanket_hook(self):
		email = _unique_email("plain")
		frappe.get_doc({"doctype": "User", "email": email, "first_name": "Plain User"}).insert(
			ignore_permissions=True
		)

		self.assertTrue(frappe.db.exists("User", email))
		self.assertFalse(frappe.db.exists("Has Role", {"parent": email, "role": GUARDIAN_ROLE}))
		self.assertEqual(frappe.get_all("Category", filters={"owner_user": email}), [])
