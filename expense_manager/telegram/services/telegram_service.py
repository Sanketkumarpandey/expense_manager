"""Minimal authenticated Telegram Bot API transport for text replies, plus the
Telegram use-case orchestrator that translates Telegram requests into domain
service calls."""

from typing import cast, Optional

import frappe
import requests
from frappe import _

from expense_manager.telegram.config import get_telegram_bot_token
from expense_manager.telegram.utils.constants import (
	_TELEGRAM_API_BASE_URL,
	SEND_MESSAGE_TIMEOUT,
	SEND_PHOTO_TIMEOUT,
	TELEGRAM_MAX_RETRIES,
	TELEGRAM_RETRY_BACKOFF_BASE,
)
from expense_manager.services.exceptions import (
	ExpenseManagerError,
	TelegramNotLinkedError,
	UnauthorizedTelegramActionError,
)
from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.services.report_service import ReportService
from expense_manager.constants.expense import ExpenseSource

from expense_manager.services.ai_service import AIService
from expense_manager.ai.exceptions import AIError


def send_message(chat_id: str | int, text: str, parse_mode: str | None = None) -> dict[str, object]:
	"""Send one text reply through Telegram without exposing credentials or adding other APIs."""
	import time

	payload: dict[str, str | int] = {"chat_id": chat_id, "text": text}
	if parse_mode is not None:
		payload["parse_mode"] = parse_mode

	last_exc: Exception | None = None
	for attempt in range(TELEGRAM_MAX_RETRIES + 1):
		try:
			response = requests.post(
				f"{_TELEGRAM_API_BASE_URL}/bot{get_telegram_bot_token()}/sendMessage",
				data=payload,
				timeout=SEND_MESSAGE_TIMEOUT,
			)
			if 500 <= response.status_code < 600 and attempt < TELEGRAM_MAX_RETRIES:
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2 ** attempt))
				continue
			response.raise_for_status()
			response_payload = response.json()
			if not isinstance(response_payload, dict):
				raise ValueError("Telegram returned an invalid sendMessage response.")
			frappe.logger("expense_manager").info("telegram_send_message status=sent")
			return cast(dict[str, object], response_payload)
		except requests.exceptions.RequestException as exc:
			last_exc = exc
			if attempt < TELEGRAM_MAX_RETRIES:
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2 ** attempt))
				continue
			raise

	raise last_exc  # type: ignore[misc]


def send_photo(chat_id: str | int, photo_bytes: bytes, caption: str | None = None) -> dict[str, object]:
	"""Send one PNG image through Telegram, with an optional caption."""
	import time

	data: dict[str, str | int] = {"chat_id": chat_id}
	if caption is not None:
		data["caption"] = caption[:1024]
	files = {"photo": ("report.png", photo_bytes, "image/png")}

	last_exc: Exception | None = None
	for attempt in range(TELEGRAM_MAX_RETRIES + 1):
		try:
			response = requests.post(
				f"{_TELEGRAM_API_BASE_URL}/bot{get_telegram_bot_token()}/sendPhoto",
				data=data,
				files=files,
				timeout=SEND_PHOTO_TIMEOUT,
			)
			if 500 <= response.status_code < 600 and attempt < TELEGRAM_MAX_RETRIES:
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2 ** attempt))
				continue
			response.raise_for_status()
			response_payload = response.json()
			if not isinstance(response_payload, dict):
				raise ValueError("Telegram returned an invalid sendPhoto response.")
			frappe.logger("expense_manager").info("telegram_send_photo status=sent")
			return cast(dict[str, object], response_payload)
		except requests.exceptions.RequestException as exc:
			last_exc = exc
			if attempt < TELEGRAM_MAX_RETRIES:
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2 ** attempt))
				continue
			raise

	raise last_exc  # type: ignore[misc]

_UNLINKED_MSG = "Your Telegram account is not linked. Use /link first."
_GUARDIAN_MSG = "This action is only available to the account guardian."


class TelegramService:

	# ------------------------------------------------------------------
	# Expense Operations
	# ------------------------------------------------------------------

	@staticmethod
	def create_expense(
		telegram_user_id: str,
		expense_data: dict,
	) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		dependent = expense_data.get("dependent")

		if identity["is_dependent"]:
			dependent = identity["dependent"]

		try:
			expense = ExpenseService.create_expense(
				owner_user=identity["owner_user"],
				category=expense_data.get("category"),
				amount=expense_data.get("amount"),
				expense_date=expense_data.get("expense_date"),
				dependent=dependent,
				description=expense_data.get("description"),
				source=ExpenseSource.TELEGRAM,
				payment_method=expense_data.get("payment_method"),
				voice_transcript=expense_data.get("voice_transcript"),
			)

			warning = TelegramService._get_overspend_warning(identity["owner_user"], expense.category)

			return {
				"success": True,
				"message": _("Expense created successfully.") + warning,
				"expense": expense.name,
			}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def update_expense(
		telegram_user_id: str,
		expense_name: str,
		updates: dict,
	) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			expense = ExpenseService.update_expense(
				owner_user=identity["owner_user"],
				expense=expense_name,
				**updates,
			)

			warning = TelegramService._get_overspend_warning(identity["owner_user"], expense.category)

			return {
				"success": True,
				"message": _("Expense updated successfully.") + warning,
				"expense": expense.name,
			}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def delete_expense(
		telegram_user_id: str,
		expense_name: str,
	) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			ExpenseService.delete_expense(identity["owner_user"], expense_name)
			return {"success": True, "message": _("Expense deleted successfully.")}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def list_expenses(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = ExpenseService.get_recent_expenses(
				identity["owner_user"],
				dependent=identity["dependent"] if identity["is_dependent"] else None,
				limit=10,
			)
			category_names = {
				row["name"]: row["category_name"]
				for row in CategoryService.list_categories(identity["owner_user"], active_only=True)
			}
			for expense in data:
				expense["category_name"] = category_names.get(expense["category"], expense["category"])
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def create_expense_from_voice(
		telegram_user_id: str,
		file_path: str,
		language_hint: Optional[str] = None,
	) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error
		dependent = identity["dependent"] if identity["is_dependent"] else None

		try:
			expense = AIService.create_expense_from_audio(
				owner_user=identity["owner_user"],
				file_path=file_path,
				dependent=dependent,
				language_hint=language_hint,
			)

			category_name = CategoryService.get_category(
				identity["owner_user"], expense.category
			).category_name

			warning = TelegramService._get_overspend_warning(identity["owner_user"], expense.category)

			return {
				"success": True,
				"message": _("Logged ₹{0} under {1}.").format(expense.amount, category_name) + warning,
				"expense": expense.name,
			}

		except (ExpenseManagerError, AIError) as exc:
			return {"success": False, "message": str(exc)}

	# ------------------------------------------------------------------
	# Reports
	# ------------------------------------------------------------------

	@staticmethod
	def get_dashboard(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = ReportService.get_dashboard_summary(identity["owner_user"])
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def get_budget(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = ReportService.get_budget_summary(identity["owner_user"])
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def get_monthly_report(
		telegram_user_id: str,
		year: Optional[int] = None,
	) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = ReportService.get_monthly_report(identity["owner_user"], year=year)
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def get_category_report(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = ReportService.get_category_breakdown(identity["owner_user"])
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def get_dependent_report(
		telegram_user_id: str,
		dependent: Optional[str] = None,
	) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		if identity["is_dependent"]:
			dependent = identity["dependent"]
		elif dependent is None:
			return {"success": False, "message": _("Please specify a dependent.")}

		try:
			data = ReportService.get_dependent_report(identity["owner_user"], dependent)
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	# ------------------------------------------------------------------
	# Dependents
	# ------------------------------------------------------------------

	@staticmethod
	def list_dependents(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = DependentService.list_dependents(identity["owner_user"], active_only=True)
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def get_pocket_money(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		try:
			if identity["is_dependent"]:
				balance = PocketMoneyService.get_balance(
					identity["owner_user"], identity["dependent"]
				)
				data = [balance] if balance else []
			else:
				data = PocketMoneyService.list_allocations(
					identity["owner_user"], active_only=True
				)

			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	# ------------------------------------------------------------------
	# Categories
	# ------------------------------------------------------------------

	@staticmethod
	def list_categories(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		try:
			data = CategoryService.list_categories(identity["owner_user"], active_only=True)
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	# ------------------------------------------------------------------
	# Account
	# ------------------------------------------------------------------

	@staticmethod
	def get_link_status(telegram_user_id: str) -> dict:
		identity = TelegramService._try_resolve_identity(telegram_user_id)

		if identity is None:
			return {"success": True, "data": {"linked": False}}

		return {
			"success": True,
			"data": {
				"linked": True,
				"is_dependent": identity["is_dependent"],
				"owner_user": identity["owner_user"],
				"dependent": identity["dependent"],
			},
		}

	@staticmethod
	def unlink_account(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_guardian_or_error(telegram_user_id)
		if error:
			return error

		try:
			TelegramLinkService.unlink_account(identity["owner_user"])
			return {"success": True, "message": _("Telegram account unlinked.")}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	# ------------------------------------------------------------------
	# Help
	# ------------------------------------------------------------------

	@staticmethod
	def get_help() -> dict:
		return {
			"success": True,
			"data": {
				"commands": [
					"start", "help", "link", "unlink", "profile",
					"expenses", "categories", "budgets", "balance",
					"report", "dependents", "pocketmoney", "savings",
					"rollover", "settings",
				]
			},
		}

	# ------------------------------------------------------------------
	# Identity Resolution (error-safe)
	# ------------------------------------------------------------------

	@staticmethod
	def _resolve_identity_or_error(telegram_user_id: str) -> tuple[Optional[dict], Optional[dict]]:
		"""Return *(identity, None)* on success, or *(None, error_dict)* if unlinked."""
		try:
			return TelegramService._resolve_identity(telegram_user_id), None
		except TelegramNotLinkedError:
			return None, {"success": False, "message": _UNLINKED_MSG}

	@staticmethod
	def _resolve_guardian_or_error(telegram_user_id: str) -> tuple[Optional[dict], Optional[dict]]:
		"""Return *(identity, None)* for a linked guardian, or *(None, error_dict)*."""
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return None, error
		try:
			TelegramService._require_guardian(identity)
			return identity, None
		except UnauthorizedTelegramActionError:
			return None, {"success": False, "message": _GUARDIAN_MSG}

	# ------------------------------------------------------------------
	# Private Helpers
	# ------------------------------------------------------------------

	@staticmethod
	def _try_resolve_identity(telegram_user_id: str) -> Optional[dict]:
		owner_user = None

		try:
			owner_user = TelegramLinkService.get_user_by_telegram(telegram_user_id)
		except TelegramNotLinkedError:
			owner_user = None

		if owner_user:
			return {
				"owner_user": owner_user,
				"dependent": None,
				"is_dependent": False,
			}

		dependent = DependentService.get_active_dependent_by_telegram_id(telegram_user_id)

		if dependent:
			return {
				"owner_user": dependent["guardian"],
				"dependent": dependent["name"],
				"is_dependent": True,
			}

		return None

	@staticmethod
	def _resolve_identity(telegram_user_id: str) -> dict:
		identity = TelegramService._try_resolve_identity(telegram_user_id)

		if identity is None:
			raise TelegramNotLinkedError(
				_("This Telegram account is not linked.")
			)

		return identity

	@staticmethod
	def _require_guardian(identity: dict) -> None:
		if identity["is_dependent"]:
			raise UnauthorizedTelegramActionError(
				_("This action is only available to the account guardian.")
			)

	@staticmethod
	def _get_overspend_warning(owner_user: str, category: str) -> str:
		try:
			usage = BudgetService.get_budget_usage(owner_user, category)
		except ExpenseManagerError:
			return ""

		if usage is None or not usage["is_overspent"]:
			return ""

		category_name = CategoryService.get_category(owner_user, category).category_name

		return _(" ⚠️ You're over budget in {0}: ₹{1} spent of ₹{2} allocated.").format(
			category_name, usage["spent_amount"], usage["allocated_amount"]
		)


	@staticmethod
	def rollover_pocket_money(telegram_user_id: str) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		if not identity["is_dependent"]:
			return {"success": False, "message": _("Only a dependent account can roll over pocket money.")}

		try:
			new_allocation = PocketMoneyService.rollover_allocation(
				identity["owner_user"], identity["dependent"]
			)
			return {
				"success": True,
				"message": _("Rolled over! New balance: ₹{0}.").format(
					new_allocation.total_available_amount
				),
			}
		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}


	@staticmethod
	def complete_link(
		telegram_user_id: str,
		token: str,
		telegram_username: Optional[str] = None,
		first_name: Optional[str] = None,
		last_name: Optional[str] = None,
		language_code: Optional[str] = None,
	) -> dict:
		try:
			TelegramLinkService.verify_and_link(
				token=token,
				telegram_user_id=telegram_user_id,
				telegram_username=telegram_username,
				first_name=first_name,
				last_name=last_name,
				language_code=language_code,
			)
			return {
				"success": True,
				"message": _("Your account is now linked! Send /help to get started."),
			}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}