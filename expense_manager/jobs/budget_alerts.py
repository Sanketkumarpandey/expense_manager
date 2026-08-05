from __future__ import annotations

import frappe

from expense_manager.services.budget_service import BudgetService
from expense_manager.services.category_service import CategoryService
from expense_manager.services.dependent_service import DependentService
from expense_manager.services.telegram_link_service import TelegramLinkService
from expense_manager.services.exceptions import (
    CategoryNotFoundError,
    ExpenseManagerError,
    TelegramNotLinkedError,
)
from expense_manager.telegram.services.telegram_service import send_message
from expense_manager.utils.logger import logger


def run_budget_alerts() -> None:
    budgets = BudgetService.list_all_active_budgets()

    notified = 0
    skipped = 0
    failed = 0

    for budget in budgets:
        dependent = budget.get("dependent")
        try:
            BudgetService.refresh_budget(budget["owner_user"], budget["category"], dependent=dependent)
            usage = BudgetService.get_budget_usage(budget["owner_user"], budget["category"], dependent=dependent)
        except ExpenseManagerError as exc:
            frappe.db.rollback()
            failed += 1
            logger.warning(
                "Budget alert check failed | budget=%s | owner=%s | category=%s | dependent=%s | error=%s",
                budget["name"], budget["owner_user"], budget["category"], dependent, str(exc),
            )
            continue

        if usage is None:
            skipped += 1
            continue

        should_notify = usage["is_overspent"] or usage["pct_used"] >= budget["alert_threshold_pct"]

        if not should_notify:
            skipped += 1
            continue

        if not BudgetService.try_claim_budget_alert(budget["owner_user"], budget["name"], dependent=dependent):
            logger.info(
                "Budget alert skipped, already sent today | budget=%s | category=%s | dependent=%s | percentage=%s",
                budget["name"], budget["category"], dependent, usage["pct_used"],
            )
            skipped += 1
            continue

        try:
            sent = _notify(budget["owner_user"], budget["category"], usage, dependent=dependent)
        except ExpenseManagerError as exc:
            frappe.db.rollback()
            failed += 1
            logger.warning(
                "Budget alert notify failed | budget=%s | owner=%s | dependent=%s | error=%s",
                budget["name"], budget["owner_user"], dependent, str(exc),
            )
            continue

        if not sent:
            skipped += 1
            continue

        frappe.db.commit()
        notified += 1
        logger.info(
            "Budget alert sent | budget=%s | owner=%s | category=%s | dependent=%s | spent=%s | allocated=%s | percentage=%s | threshold=%s",
            budget["name"], budget["owner_user"], budget["category"], dependent,
            usage["spent_amount"], usage["allocated_amount"], usage["pct_used"], budget["alert_threshold_pct"],
        )

    logger.info(
        "Budget alerts run complete | notified=%s | skipped=%s | failed=%s",
        notified, skipped, failed,
    )


def _notify(owner_user: str, category: str, usage: dict, dependent: str | None = None) -> bool:
    """
    Send a budget alert to the guardian via Telegram.

    Decision note: Dependent-scoped budgets are routed to the guardian's
    Telegram chat (dependents have no TelegramLink today). The alert
    message includes the dependent's name so the guardian knows who the
    alert applies to. If a future phase adds delivery channels for
    dependents, this function should be extended to route there instead.
    """
    try:
        link = TelegramLinkService.get_link(owner_user)
    except TelegramNotLinkedError:
        return False

    try:
        category_doc = CategoryService.get_category(owner_user, category)
    except CategoryNotFoundError:
        raise ExpenseManagerError(frappe._("Category not found."))

    category_name = category_doc.category_name
    message = BudgetService.build_budget_alert_message(category_name, usage)

    if dependent:
        dependent_name = frappe.db.get_value("Dependent", dependent, "dependent_name")
        if dependent_name:
            message = f"[{dependent_name}] {message}"

    send_message(link.telegram_user_id, message)
    return True