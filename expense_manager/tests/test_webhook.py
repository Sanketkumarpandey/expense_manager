"""Unit tests for Telegram webhook infrastructure without Telegram network calls."""

from unittest import TestCase
from unittest.mock import MagicMock, patch

import frappe

from expense_manager.config.exceptions import ConfigurationError
from expense_manager.telegram import webhook


class TestTelegramWebhook(TestCase):
	"""Verify webhook validation, deduplication, and no-op queue behavior."""

	def setUp(self) -> None:
		"""Create a safe synthetic request and Redis cache for each test."""
		self.request = MagicMock()
		self.request.headers = {"X-Telegram-Bot-Api-Secret-Token": "expected-secret"}
		self.cache = MagicMock()
		self.cache.make_key.side_effect = lambda key, shared: key
		self.cache.set.return_value = True
		self.patches = (
			patch.object(webhook.frappe, "request", self.request),
			patch.object(webhook.frappe, "cache", return_value=self.cache),
			patch("expense_manager.telegram.webhook.get_telegram_webhook_secret", return_value="expected-secret"),
			patch.object(webhook.frappe, "enqueue"),
			patch.object(webhook.frappe, "logger"),
		)
		for active_patch in self.patches:
			active_patch.start()

	def tearDown(self) -> None:
		"""Stop request, cache, queue, and logger patches after each test."""
		for active_patch in reversed(self.patches):
			active_patch.stop()

	def test_valid_webhook_enqueues_background_job_and_returns_ok(self) -> None:
		"""Accept a valid update, reserve it, and enqueue its no-op worker."""
		self.request.get_json.return_value = {"update_id": 101, "message": {}}

		self.assertEqual(webhook.handle(), {"ok": True})
		frappe.enqueue.assert_called_once_with(
			method="expense_manager.telegram.webhook.process_update",
			queue="short",
			update={"update_id": 101, "message": {}},
		)
		self.cache.set.assert_called_once()

	def test_invalid_secret_is_rejected_without_enqueuing(self) -> None:
		"""Reject an invalid Telegram secret with Frappe's HTTP-403 exception."""
		self.request.headers = {"X-Telegram-Bot-Api-Secret-Token": "incorrect-secret"}

		with self.assertRaises(frappe.PermissionError) as error:
			webhook.handle()

		self.assertEqual(error.exception.http_status_code, 403)
		frappe.enqueue.assert_not_called()

	def test_missing_secret_configuration_fails_closed_without_enqueuing(self) -> None:
		"""Return a safe service error when the required webhook secret is absent."""
		with patch(
			"expense_manager.telegram.webhook.get_telegram_webhook_secret",
			side_effect=ConfigurationError("missing configuration"),
		):
			with self.assertRaises(frappe.ServiceUnavailableError) as error:
				webhook.handle()

		self.assertEqual(error.exception.http_status_code, 503)
		frappe.enqueue.assert_not_called()

	def test_malformed_payload_is_not_enqueued_and_is_acknowledged(self) -> None:
		"""Acknowledge malformed JSON without enqueueing a retryable Telegram update."""
		self.request.get_json.side_effect = ValueError("invalid JSON")

		self.assertEqual(webhook.handle(), {"ok": True})
		frappe.enqueue.assert_not_called()

	def test_duplicate_update_is_not_enqueued_twice(self) -> None:
		"""Acknowledge an already-reserved update without creating a second job."""
		self.request.get_json.return_value = {"update_id": 102, "edited_message": {}}
		self.cache.set.return_value = False

		self.assertEqual(webhook.handle(), {"ok": True})
		frappe.enqueue.assert_not_called()

	def test_missing_update_id_is_not_enqueued(self) -> None:
		"""Acknowledge a payload lacking update_id without reserving or processing it."""
		self.request.get_json.return_value = {"message": {}}

		self.assertEqual(webhook.handle(), {"ok": True})
		self.cache.set.assert_not_called()
		frappe.enqueue.assert_not_called()

	def test_enqueue_failure_releases_update_for_a_telegram_retry(self) -> None:
		"""Release an update ID and return a safe retryable error when queueing fails."""
		self.request.get_json.return_value = {"update_id": 104, "message": {}}
		frappe.enqueue.side_effect = RuntimeError("queue unavailable")

		with self.assertRaises(frappe.ServiceUnavailableError) as error:
			webhook.handle()

		self.assertEqual(error.exception.http_status_code, 503)
		self.cache.delete.assert_called_once()

	def test_background_worker_is_a_no_op(self) -> None:
		"""Delegate queued execution to the command worker without routing in the webhook module."""
		with patch("expense_manager.telegram.bot.process_update") as dispatch_update:
			self.assertIsNone(webhook.process_update({"update_id": 103, "message": {}}))

		dispatch_update.assert_called_once_with({"update_id": 103, "message": {}})

	def test_endpoint_is_guest_whitelisted_for_post_requests(self) -> None:
		"""Expose the endpoint through Frappe's whitelisted-method mechanism."""
		self.assertIn(webhook.handle, frappe.whitelisted)
		self.assertIn(webhook.handle, frappe.guest_methods)
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[webhook.handle], ["POST"])
