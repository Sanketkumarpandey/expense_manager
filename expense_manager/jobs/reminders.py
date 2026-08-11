from __future__ import annotations

import frappe

from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.report_service import ReportService
from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.telegram.services.telegram_service import send_message
from expense_manager.utils.logger import logger


def run_reminders() -> None:
	"""Daily scheduler entry point.

	Enumerates every active Telegram link and, for each linked user,
	checks which reminders apply.  Business logic (date calculations,
	message formatting, threshold checks) lives entirely in
	ReportService and PocketMoneyService — this job only orchestrates
	the look-up and dispatch.
	"""
	links = TelegramLinkService.list_links(active_only=True)

	sent = 0
	skipped = 0
	failed = 0

	for link in links:
		telegram_user_id = link.get("telegram_user_id")
		owner_user = link.get("user")

		if not telegram_user_id or not owner_user:
			skipped += 1
			continue

		try:
			messages = _collect_reminders(owner_user)
		except ExpenseManagerError:
			failed += 1
			logger.warning(
				"Reminder collection failed | owner=%s | error=service error",
				owner_user,
			)
			continue

		for message in messages:
			try:
				send_message(telegram_user_id, message)
				frappe.db.commit()
				sent += 1
			except Exception:
				frappe.db.rollback()
				failed += 1
				logger.warning(
					"Reminder send failed | owner=%s | telegram_user_id=%s",
					owner_user,
					telegram_user_id,
				)

	logger.info(
		"Reminders run complete | sent=%s | skipped=%s | failed=%s",
		sent,
		skipped,
		failed,
	)


def _collect_reminders(owner_user: str) -> list[str]:
	"""Gather all applicable reminder messages for one user.

	Each call delegates to a service method that owns the business
	rule (date checks, thresholds, formatting).  This function simply
	collects the non-None / non-empty results.
	"""
	messages: list[str] = []

	# 1. No expenses today
	no_expenses_msg = ReportService.build_no_expenses_today_message(owner_user)
	if no_expenses_msg:
		messages.append(no_expenses_msg)

	# 2. Weekly summary
	weekly_msg = ReportService.build_weekly_summary_message(owner_user)
	if weekly_msg:
		messages.append(weekly_msg)

	# 3. Monthly summary
	monthly_msg = ReportService.build_monthly_summary_message(owner_user)
	if monthly_msg:
		messages.append(monthly_msg)

	# 4. Pocket money ending soon
	low_balance_msgs = PocketMoneyService.build_low_balance_messages(owner_user)
	messages.extend(low_balance_msgs)

	return messages
