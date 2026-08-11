"""Authenticated, asynchronous Telegram webhook ingress without update routing."""

import hmac
from time import perf_counter

import frappe

from expense_manager.config.exceptions import ConfigurationError
from expense_manager.telegram.config import get_telegram_webhook_secret

_DEDUPLICATION_TTL_SECONDS = 24 * 60 * 60
_SECRET_HEADER = "X-Telegram-Bot-Api-Secret-Token"


@frappe.whitelist(allow_guest=True, methods=["POST"])
def handle() -> dict[str, bool]:
	"""Validate and enqueue one Telegram update; it does not route or process it."""
	started_at = perf_counter()
	try:
		_verify_secret_token()
	except ConfigurationError:
		_log_webhook_event(None, "configuration_error", started_at)
		raise frappe.ServiceUnavailableError("Telegram webhook configuration is unavailable.")
	except frappe.PermissionError:
		_log_webhook_event(None, "rejected_invalid_secret", started_at)
		raise

	update = _read_update()
	if update is None:
		_log_webhook_event(None, "rejected_invalid_payload", started_at)
		return {"ok": True}

	update_id = update.get("update_id")
	if not _is_valid_update_id(update_id):
		_log_webhook_event(update, "rejected_missing_update_id", started_at)
		return {"ok": True}

	if not _claim_update(update_id):
		_log_webhook_event(update, "duplicate", started_at)
		return {"ok": True}

	try:
		frappe.enqueue(
			method="expense_manager.telegram.webhook.process_update",
			queue="short",
			update=update,
		)
	except Exception:
		_release_update(update_id)
		frappe.logger("expense_manager").exception("telegram_webhook_enqueue_failed update_id=%s", update_id)
		_log_webhook_event(update, "enqueue_failed", started_at)
		raise frappe.ServiceUnavailableError("Unable to queue the Telegram update.")

	_log_webhook_event(update, "enqueued", started_at)
	return {"ok": True}


def process_update(update: dict[str, object]) -> None:
	"""Delegate a validated queued update to the command-only bot dispatcher."""
	from expense_manager.telegram.bot import process_update as dispatch_update

	dispatch_update(update)


def _verify_secret_token() -> None:
	"""Reject a request whose configured Telegram secret does not match its header."""
	provided_secret = frappe.request.headers.get(_SECRET_HEADER, "")
	expected_secret = get_telegram_webhook_secret()
	if not isinstance(provided_secret, str) or not hmac.compare_digest(provided_secret, expected_secret):
		raise frappe.PermissionError("Invalid Telegram webhook secret.")


def _read_update() -> dict[str, object] | None:
	"""Safely parse and validate the JSON object sent by Telegram."""
	try:
		update = frappe.request.get_json()
	except Exception:
		return None
	return update if isinstance(update, dict) else None


def _is_valid_update_id(update_id: object) -> bool:
	"""Return whether a payload contains a Telegram numeric update identifier."""
	return isinstance(update_id, int) and not isinstance(update_id, bool)


def _claim_update(update_id: int) -> bool:
	"""Atomically reserve an update ID for one day to prevent duplicate processing."""
	cache = frappe.cache()
	cache_key = cache.make_key(_get_deduplication_key(update_id), shared=True)
	return bool(cache.set(cache_key, "1", ex=_DEDUPLICATION_TTL_SECONDS, nx=True))


def _release_update(update_id: int) -> None:
	"""Release a reserved update ID when enqueueing fails before a job is created."""
	cache = frappe.cache()
	cache_key = cache.make_key(_get_deduplication_key(update_id), shared=True)
	cache.delete(cache_key)


def _get_deduplication_key(update_id: int) -> str:
	"""Build a site-specific Redis key for one Telegram update identifier."""
	return f"{frappe.local.site}:expense_manager:telegram_update:{update_id}"


def _log_webhook_event(update: dict[str, object] | None, status: str, started_at: float) -> None:
	"""Log safe webhook metadata without logging a payload or secret values."""
	update_id = update.get("update_id") if update else None
	frappe.logger("expense_manager").info(
		"telegram_webhook update_id=%s update_type=%s status=%s latency_ms=%d",
		update_id,
		_get_update_type(update),
		status,
		int((perf_counter() - started_at) * 1000),
	)


def _get_update_type(update: dict[str, object] | None) -> str:
	"""Return a safe top-level Telegram update type without inspecting message content."""
	if not update:
		return "unknown"
	return next((key for key in update if key != "update_id"), "unknown")
