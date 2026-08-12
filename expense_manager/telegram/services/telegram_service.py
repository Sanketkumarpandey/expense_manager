"""Minimal authenticated Telegram Bot API transport for text replies, plus the
Telegram use-case orchestrator that translates Telegram requests into domain
service calls."""

from typing import Optional, cast

import frappe
import requests
from frappe import _
from frappe.utils import flt

from expense_manager.ai.exceptions import AIError
from expense_manager.config.exceptions import ConfigurationError
from expense_manager.constants.expense import ExpenseSource
from expense_manager.services.ai_service import AIService
from expense_manager.services.budget_service import BudgetService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.exceptions import (
	ExpenseManagerError,
	TelegramNotLinkedError,
	UnauthorizedTelegramActionError,
)
from expense_manager.services.expense_service import ExpenseService
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.report_service import ReportService
from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.telegram.config import get_telegram_bot_token
from expense_manager.telegram.utils.constants import (
	_TELEGRAM_API_BASE_URL,
	SEND_MESSAGE_TIMEOUT,
	SEND_PHOTO_TIMEOUT,
	TELEGRAM_MAX_RETRIES,
	TELEGRAM_RETRY_BACKOFF_BASE,
)


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
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2**attempt))
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
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2**attempt))
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
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2**attempt))
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
				time.sleep(TELEGRAM_RETRY_BACKOFF_BASE * (2**attempt))
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
			if identity["is_dependent"]:
				PocketMoneyService.enforce_available_balance(
					identity["owner_user"],
					identity["dependent"],
					flt(expense_data.get("amount", 0)),
				)

			category = expense_data.get("category")

			if identity["is_dependent"]:
				allowed_ids = {
					row["name"]
					for row in DependentService.list_allowed_categories(
						identity["owner_user"], identity["dependent"], active_only=True
					)
				}
				if category not in allowed_ids:
					return {
						"success": False,
						"message": _("That category is not allowed for your account."),
					}

			expense = ExpenseService.create_expense(
				owner_user=identity["owner_user"],
				category=category,
				amount=expense_data.get("amount"),
				expense_date=expense_data.get("expense_date"),
				dependent=dependent,
				description=expense_data.get("description"),
				source=ExpenseSource.TELEGRAM,
				payment_method=expense_data.get("payment_method"),
				voice_transcript=expense_data.get("voice_transcript"),
			)

			warning = TelegramService._get_overspend_warning(
				identity["owner_user"], expense.category, dependent=dependent
			)

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

			warning = TelegramService._get_overspend_warning(
				identity["owner_user"], expense.category, dependent=expense.dependent
			)

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
			is_dep = identity["is_dependent"]
			category_map = {
				row["name"]: row
				for row in CategoryService.list_categories(
					identity["owner_user"],
					active_only=True,
					dependent=identity["dependent"] if is_dep else None,
					include_all=not is_dep,
				)
			}
			for expense in data:
				cat = category_map.get(expense["category"])
				if cat:
					expense["category_name"] = cat["category_name"]
					expense["category_icon"] = (cat.get("icon") or "").strip()
				else:
					expense["category_name"] = expense["category"]
					expense["category_icon"] = ""
			return {"success": True, "data": data}

		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def build_expenses_display(telegram_user_id: str) -> str:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error["message"]

		owner_user = identity["owner_user"]

		if identity["is_dependent"]:
			expenses = ExpenseService.get_recent_expenses(
				owner_user, dependent=identity["dependent"], limit=10
			)
			if not expenses:
				return "You don't have any recent expenses."
			category_map = {
				row["name"]: row
				for row in DependentService.list_allowed_categories(
					owner_user, identity["dependent"], active_only=True
				)
			}
			for e in expenses:
				cat = category_map.get(e["category"])
				if cat:
					e["category_name"] = cat["category_name"]
					e["category_icon"] = (cat.get("icon") or "").strip()
				else:
					e["category_name"] = e["category"]
					e["category_icon"] = ""
			return TelegramService._format_flat_expenses(expenses)

		deps = DependentService.list_dependents(owner_user, active_only=True)
		all_cats = {row["name"]: row for row in CategoryService.list_categories(owner_user, active_only=True)}

		groups: list[tuple[str, list[dict]]] = []

		# The guardian's own bucket must exclude dependent-scoped expenses
		# (dependent not set), otherwise each dependent's spend also shows
		# up as the guardian's personal spend.
		own = ExpenseService.get_recent_expenses(owner_user, dependent=["is", "not set"], limit=10)
		for e in own:
			cat = all_cats.get(e["category"])
			if cat:
				e["category_name"] = cat["category_name"]
				e["category_icon"] = (cat.get("icon") or "").strip()
			else:
				e["category_name"] = e["category"]
				e["category_icon"] = ""
		if own:
			groups.append(("You", own))

		for dep in deps:
			dep_exp = ExpenseService.get_recent_expenses(owner_user, dependent=dep["name"], limit=10)
			for e in dep_exp:
				cat = all_cats.get(e["category"])
				if cat:
					e["category_name"] = cat["category_name"]
					e["category_icon"] = (cat.get("icon") or "").strip()
				else:
					e["category_name"] = e["category"]
					e["category_icon"] = ""
			if dep_exp:
				groups.append((dep["dependent_name"], dep_exp))

		if not groups:
			return "You don't have any recent expenses."

		if len(groups) == 1:
			return TelegramService._format_flat_expenses(groups[0][1])

		lines = ["Your recent expenses:"]
		grand_total = 0
		for person, expenses in groups:
			total = sum(e["amount"] for e in expenses)
			grand_total += total
			lines.append("")
			lines.append(f"\U0001f464 {person}")
			for e in expenses:
				d = e.get("expense_date", "")
				icon = e.get("category_icon", "")
				cat = e.get("category_name", "")
				icon_prefix = f"{icon} " if icon else ""
				amt = int(e["amount"])
				lines.append(f"{d} | {icon_prefix}{cat} | \u20b9{amt}")
			lines.append(f"  Total: \u20b9{int(total)}")

		lines.append("")
		lines.append(f"Grand total: \u20b9{int(grand_total)}")
		return "\n".join(lines)

	@staticmethod
	def _format_flat_expenses(expenses: list[dict]) -> str:
		total = sum(e["amount"] for e in expenses)
		lines = ["Your recent expenses:"]
		for e in expenses:
			d = e.get("expense_date", "")
			icon = e.get("category_icon", "")
			cat = e.get("category_name", "")
			icon_prefix = f"{icon} " if icon else ""
			amt = int(e["amount"])
			lines.append(f"{d} | {icon_prefix}{cat} | \u20b9{amt}")
		lines.append(f"  Total: \u20b9{int(total)}")
		return "\n".join(lines)

	@staticmethod
	def create_expense_from_voice(
		telegram_user_id: str,
		file_path: str,
		language_hint: str | None = None,
	) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		try:
			expense = AIService.create_expense_from_audio(
				owner_user=identity["owner_user"],
				file_path=file_path,
				dependent=identity["dependent"] if identity["is_dependent"] else None,
				language_hint=language_hint,
			)

			exp_dependent = getattr(expense, "dependent", None)

			category_doc = CategoryService.get_category(identity["owner_user"], expense.category)
			category_name = category_doc.category_name
			category_icon = (category_doc.icon or "").strip()

			warning = TelegramService._get_overspend_warning(
				identity["owner_user"], expense.category, dependent=exp_dependent
			)

			icon_prefix = f"{category_icon} " if category_icon else ""

			return {
				"success": True,
				"message": _("Logged ₹{0} under {1}{2}.").format(expense.amount, icon_prefix, category_name)
				+ warning,
				"expense": expense.name,
			}

		except (ExpenseManagerError, AIError) as exc:
			return {"success": False, "message": str(exc)}
		except ConfigurationError:
			frappe.logger("expense_manager").exception("telegram_service status=config_error")
			return {
				"success": False,
				"message": _("AI expense parsing isn't set up yet. Please contact your administrator."),
			}

	@staticmethod
	def create_expense_from_text(
		telegram_user_id: str,
		text: str,
	) -> dict:
		identity, error = TelegramService._resolve_identity_or_error(telegram_user_id)
		if error:
			return error

		try:
			expense = AIService.create_expense_from_text(
				owner_user=identity["owner_user"],
				text=text,
				dependent=identity["dependent"] if identity["is_dependent"] else None,
			)

			exp_dependent = getattr(expense, "dependent", None)

			category_doc = CategoryService.get_category(identity["owner_user"], expense.category)
			category_name = category_doc.category_name
			category_icon = (category_doc.icon or "").strip()

			warning = TelegramService._get_overspend_warning(
				identity["owner_user"], expense.category, dependent=exp_dependent
			)

			icon_prefix = f"{category_icon} " if category_icon else ""

			return {
				"success": True,
				"message": _("Logged ₹{0} under {1}{2}.").format(expense.amount, icon_prefix, category_name)
				+ warning,
				"expense": expense.name,
			}

		except (ExpenseManagerError, AIError) as exc:
			return {"success": False, "message": str(exc)}
		except ConfigurationError:
			frappe.logger("expense_manager").exception("telegram_service status=config_error")
			return {
				"success": False,
				"message": _("AI expense parsing isn't set up yet. Please contact your administrator."),
			}

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
		year: int | None = None,
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
		dependent: str | None = None,
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
				balance = PocketMoneyService.get_balance(identity["owner_user"], identity["dependent"])
				data = [balance] if balance else []
			else:
				data = PocketMoneyService.list_allocations(identity["owner_user"], active_only=True)

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
			if identity["is_dependent"]:
				data = DependentService.list_allowed_categories(
					identity["owner_user"],
					identity["dependent"],
					active_only=True,
				)
			else:
				data = CategoryService.list_categories(
					identity["owner_user"],
					active_only=True,
				)
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
		from expense_manager.telegram.router import COMMAND_DESCRIPTIONS

		commands = [cmd for section in COMMAND_DESCRIPTIONS.values() for cmd, _ in section]
		return {
			"success": True,
			"data": {"commands": commands},
		}

	# ------------------------------------------------------------------
	# Identity Resolution (error-safe)
	# ------------------------------------------------------------------

	@staticmethod
	def _resolve_identity_or_error(telegram_user_id: str) -> tuple[dict | None, dict | None]:
		"""Return *(identity, None)* on success, or *(None, error_dict)* if unlinked."""
		try:
			return TelegramService._resolve_identity(telegram_user_id), None
		except TelegramNotLinkedError:
			return None, {"success": False, "message": _UNLINKED_MSG}

	@staticmethod
	def _resolve_guardian_or_error(telegram_user_id: str) -> tuple[dict | None, dict | None]:
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
	def _try_resolve_identity(telegram_user_id: str) -> dict | None:
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
			raise TelegramNotLinkedError(_("This Telegram account is not linked."))

		return identity

	@staticmethod
	def _require_guardian(identity: dict) -> None:
		if identity["is_dependent"]:
			raise UnauthorizedTelegramActionError(_("This action is only available to the account guardian."))

	@staticmethod
	def _get_overspend_warning(owner_user: str, category: str, dependent: str | None = None) -> str:
		return BudgetService.build_inline_overspend_warning(owner_user, category, dependent=dependent)

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
			dep_doc = DependentService.get_dependent(identity["owner_user"], identity["dependent"])
			savings = dep_doc.get("total_savings", 0) or 0
			return {
				"success": True,
				"message": _("Rolled over! Spendable: ₹{0}. Total savings: ₹{1}.").format(
					new_allocation.total_available_amount,
					savings,
				),
			}
		except ExpenseManagerError as exc:
			return {"success": False, "message": str(exc)}

	@staticmethod
	def complete_link(
		telegram_user_id: str,
		token: str,
		telegram_username: str | None = None,
		first_name: str | None = None,
		last_name: str | None = None,
		language_code: str | None = None,
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
