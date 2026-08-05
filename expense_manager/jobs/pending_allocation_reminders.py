from __future__ import annotations

import frappe

from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.services.exceptions import ExpenseManagerError, TelegramNotLinkedError
from expense_manager.telegram.services.telegram_service import send_message
from expense_manager.utils.logger import logger


def run_pending_allocation_reminders() -> None:
    """
    Daily scheduled entry point.

    For every dependent flagged with pending_allocation_since:
    1. Skip if they already have an active allocation with amount > 0
       (clears the pending flag as a side effect).
    2. Skip if the guardian has no Telegram link.
    3. Skip if a reminder was already sent today.
    4. Otherwise send the reminder and mark it sent.
    """
    dependents = PocketMoneyService.list_dependents_pending_allocation()

    notified = 0
    skipped = 0
    failed = 0

    for dep in dependents:
        guardian = dep["guardian"]

        # 1. Guardian must have a Telegram link
        try:
            link = TelegramLinkService.get_link(guardian)
        except TelegramNotLinkedError:
            skipped += 1
            continue

        # 2. Check if a positive allocation already exists (stale flag cleanup)
        allocation = PocketMoneyService.get_balance(guardian, dep["name"])
        if allocation and allocation.get("allocated_amount", 0) > 0:
            PocketMoneyService._clear_pending_allocation_on_dependent(dep["name"])
            skipped += 1
            continue

        # 3. Dedup within the same day
        if not PocketMoneyService.try_claim_pending_allocation_reminder(dep["name"]):
            skipped += 1
            continue

        # 4. Send
        try:
            savings = dep.get("total_savings", 0) or 0
            message = (
                f"\U0001f514 {dep['dependent_name']}'s pocket money rolled over. "
                f"Savings: \u20b9{savings}. "
                f"Please assign next month's pocket money."
            )
            send_message(link.telegram_user_id, message)
            frappe.db.commit()
            notified += 1
        except Exception:
            frappe.db.rollback()
            failed += 1
            logger.warning(
                "Pending allocation reminder send failed | dependent=%s | guardian=%s",
                dep["name"], guardian,
            )

    logger.info(
        "Pending allocation reminders run complete | notified=%s | skipped=%s | failed=%s",
        notified, skipped, failed,
    )
