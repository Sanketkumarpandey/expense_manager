from __future__ import annotations

from typing import Optional

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, add_days, add_months, today as frappe_today

from expense_manager.services.exceptions import (
    DependentNotFoundError,
    PocketMoneyAllocationNotFoundError,
    PocketMoneyAllocationAlreadyExistsError,
    PocketMoneyNotAllocatedError,
    PocketMoneyExceededError,
    InvalidAllocationAmountError,
    InvalidAllocationPeriodError,
    InvalidAllocationDateError,
    InvalidCarryForwardAmountError,
)
from expense_manager.services.dependent_service import DependentService
from expense_manager.constants.pocket_money import AllocationPeriod
from expense_manager.utils.logger import logger
from expense_manager.utils.helpers import escape_like


_UNSET = object()


class PocketMoneyService:

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @staticmethod
    def create_allocation(
        guardian: str,
        dependent: str,
        allocated_amount: float,
        allocation_period: str,
        allocation_date=None,
        carry_forward_amount: float = 0.0,
        remarks: Optional[str] = None,
    ) -> Document:
        PocketMoneyService._validate_dependent(guardian, dependent)
        PocketMoneyService._validate_period(allocation_period)
        allocated_amount = PocketMoneyService._validate_amount(allocated_amount)
        carry_forward_amount = PocketMoneyService._validate_carry_forward(
            carry_forward_amount
        )

        if allocation_date is None:
            allocation_date = frappe_today()
        PocketMoneyService._validate_dates(allocation_date)

        if PocketMoneyService._get_active_allocation_for_dependent(dependent) is not None:
            raise PocketMoneyAllocationAlreadyExistsError(
                _("An active pocket money allocation already exists for this dependent.")
            )

        allocation = frappe.get_doc(
            {
                "doctype": "Pocket Money Allocation",
                "dependent": dependent,
                "allocation_period": allocation_period,
                "allocated_amount": allocated_amount,
                "allocation_date": allocation_date,
                "carry_forward_amount": carry_forward_amount,
                "total_available_amount": allocated_amount + carry_forward_amount,
                "remarks": remarks,
                "is_active": 1,
            },
            ignore_permissions=True,
        )

        allocation.insert(ignore_permissions=True)

        PocketMoneyService.refresh_balance(guardian, dependent)

        if allocated_amount > 0:
            PocketMoneyService._clear_pending_allocation_on_dependent(dependent)

        logger.info(
            "Pocket money allocation created | guardian=%s | dependent=%s | id=%s | allocated=%s",
            guardian,
            dependent,
            allocation.name,
            allocated_amount,
        )

        return allocation

    @staticmethod
    def get_allocation(
        guardian: str,
        allocation: str,
    ) -> Document:
        return PocketMoneyService._get_allocation(guardian, allocation)

    @staticmethod
    def update_allocation(
        guardian: str,
        allocation: str,
        allocated_amount: Optional[float] = None,
        allocation_period: Optional[str] = None,
        allocation_date=None,
        carry_forward_amount: Optional[float] = None,
        remarks: str | None | object = _UNSET,
    ) -> Document:
        doc = PocketMoneyService._get_allocation(guardian, allocation)

        if allocated_amount is not None:
            doc.allocated_amount = PocketMoneyService._validate_amount(allocated_amount)

        if allocation_period is not None:
            PocketMoneyService._validate_period(allocation_period)
            doc.allocation_period = allocation_period

        if allocation_date is not None:
            PocketMoneyService._validate_dates(allocation_date)
            doc.allocation_date = allocation_date

        if carry_forward_amount is not None:
            doc.carry_forward_amount = PocketMoneyService._validate_carry_forward(
                carry_forward_amount
            )

        if remarks is not _UNSET:
            doc.remarks = remarks

        doc.save(ignore_permissions=True)

        PocketMoneyService.refresh_balance(guardian, doc.dependent)

        logger.info(
            "Pocket money allocation updated | guardian=%s | id=%s",
            guardian,
            doc.name,
        )

        return doc

    @staticmethod
    def delete_allocation(
        guardian: str,
        allocation: str,
    ) -> None:
        doc = PocketMoneyService._get_allocation(guardian, allocation)

        PocketMoneyService._validate_delete(doc)

        doc.delete(ignore_permissions=True)

        logger.info(
            "Pocket money allocation deleted | guardian=%s | id=%s",
            guardian,
            doc.name,
        )

    @staticmethod
    def archive_allocation(
        guardian: str,
        allocation: str,
    ) -> Document:
        return PocketMoneyService._set_active_status(guardian, allocation, False)

    @staticmethod
    def restore_allocation(
        guardian: str,
        allocation: str,
    ) -> Document:
        return PocketMoneyService._set_active_status(guardian, allocation, True)

    @staticmethod
    def list_allocations(
        guardian: str,
        dependent: Optional[str] = None,
        active_only: bool = False,
    ) -> list[dict]:
        if dependent is not None:
            PocketMoneyService._validate_dependent(guardian, dependent)
            filters = {"dependent": dependent}
        else:
            filters = {
                "dependent": ["in", PocketMoneyService._guardian_dependent_names(guardian)]
            }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Pocket Money Allocation",
            filters=filters,
            fields=[
                "name",
                "dependent",
                "allocation_period",
                "allocated_amount",
                "allocation_date",
                "carry_forward_amount",
                "total_available_amount",
                "is_active",
                "creation",
                "modified",
            ],
            order_by="allocation_date desc",
        )

    @staticmethod
    def search_allocations(
        guardian: str,
        search_text: Optional[str],
        active_only: bool = True,
    ) -> list[dict]:
        if not search_text:
            return []

        filters = {
            "dependent": ["in", PocketMoneyService._guardian_dependent_names(guardian)],
            "remarks": ["like", f"%{escape_like(search_text.strip())}%"],
        }

        if active_only:
            filters["is_active"] = 1

        return frappe.get_all(
            "Pocket Money Allocation",
            filters=filters,
            fields=[
                "name",
                "dependent",
                "allocated_amount",
                "total_available_amount",
            ],
            order_by="allocation_date desc",
        )

    # ------------------------------------------------------------------
    # Balance
    # ------------------------------------------------------------------

    @staticmethod
    def get_balance(
        guardian: str,
        dependent: str,
    ) -> Optional[dict]:
        """
        Returns the current pocket money position for a dependent, or
        None if the dependent has no active allocation.

        spent_amount is always computed live from Expense records —
        it is never persisted. total_available_amount on the Pocket
        Money Allocation doc is only a cached copy of remaining_amount,
        refreshed by refresh_balance().
        """
        PocketMoneyService._validate_dependent(guardian, dependent)

        allocation = PocketMoneyService._get_active_allocation_for_dependent(dependent)

        if allocation is None:
            return None

        period_end = PocketMoneyService.get_period_end_date(
            allocation.allocation_date,
            allocation.allocation_period,
        )

        spent_amount = PocketMoneyService._calculate_spent_amount(
            guardian,
            dependent,
            allocation.allocation_date,
            period_end,
        )

        allocated_val = round(flt(allocation.allocated_amount), 2)
        spent_val = round(flt(spent_amount), 2)
        carry_val = round(flt(allocation.carry_forward_amount), 2)
        remaining_amount = round(allocated_val + carry_val - spent_val, 2)

        dependent_doc = DependentService.get_dependent(guardian, dependent)

        return {
            "allocation": allocation.name,
            "allocated_amount": allocated_val,
            "spent_amount": spent_val,
            "carry_forward": carry_val,
            "remaining_amount": remaining_amount,
            "available_amount": max(0.0, remaining_amount),
            "total_savings": round(flt(getattr(dependent_doc, "total_savings", 0)), 2),
        }

    @staticmethod
    def refresh_balance(
        owner_user: str,
        dependent: Optional[str],
    ) -> None:
        """
        Recomputes and persists total_available_amount for the
        dependent's active allocation. Called by ExpenseService after
        every create/update/delete of an expense. A no-op when the
        expense has no dependent, or the dependent has no active
        allocation — matches BudgetService.refresh_budget's shape.
        """
        if not dependent:
            return

        PocketMoneyService._validate_dependent(owner_user, dependent)

        allocation = PocketMoneyService._get_active_allocation_for_dependent(dependent)

        if allocation is None:
            return

        period_end = PocketMoneyService.get_period_end_date(
            allocation.allocation_date,
            allocation.allocation_period,
        )

        spent_amount = PocketMoneyService._calculate_spent_amount(
            owner_user,
            dependent,
            allocation.allocation_date,
            period_end,
        )

        remaining_amount = max(
            0,
            allocation.allocated_amount + allocation.carry_forward_amount - spent_amount,
        )

        allocation.total_available_amount = remaining_amount
        allocation.save(ignore_permissions=True)

        logger.info(
            "Pocket money balance refreshed | owner=%s | dependent=%s | id=%s | remaining=%s",
            owner_user,
            dependent,
            allocation.name,
            remaining_amount,
        )

    @staticmethod
    def enforce_available_balance(
        guardian: str,
        dependent: str,
        amount: float,
    ) -> None:
        """Hard-block: raise unless the dependent's live pocket money can
        cover the expense amount. Raised when the balance is exhausted or no
        active allocation exists (e.g. a zero-amount post-rollover placeholder
        awaiting a top-up). Call before creating the expense.
        """
        balance = PocketMoneyService.get_balance(guardian, dependent)

        if balance is None:
            raise PocketMoneyNotAllocatedError(
                _("You don't have any pocket money yet. Ask your guardian to top you up.")
            )

        available = flt(balance.get("available_amount", 0))
        if available < amount:
            raise PocketMoneyExceededError(
                _("Not enough pocket money: ₹{0} available but this costs ₹{1}. Ask your guardian to top you up.").format(
                    available, amount
                )
            )

    # ------------------------------------------------------------------
    # Notification message builders (called by jobs/reminders.py)
    # ------------------------------------------------------------------

    LOW_BALANCE_THRESHOLD = 0.2

    @staticmethod
    def build_low_balance_messages(owner_user: str) -> list[str]:
        """Return one message per dependent whose pocket money is running low.

        A balance is considered "low" when the remaining amount falls
        below 20 % of the allocated amount.
        """
        dependents = DependentService.list_dependents(owner_user, active_only=True)
        messages: list[str] = []

        for dep in dependents:
            balance = PocketMoneyService.get_balance(owner_user, dep["name"])
            if balance is None:
                continue

            allocated = balance.get("allocated_amount", 0)
            remaining = balance.get("remaining_amount", 0)

            if allocated > 0 and remaining < allocated * PocketMoneyService.LOW_BALANCE_THRESHOLD:
                messages.append(
                    f"Pocket money for {dep['dependent_name']} is running low: "
                    f"{remaining} remaining of {allocated} allocated."
                )

        return messages

    # ------------------------------------------------------------------
    # Pending allocation reminders (called by jobs/pending_allocation_reminders.py)
    # ------------------------------------------------------------------

    @staticmethod
    def list_dependents_pending_allocation() -> list[dict]:
        """System-level only — returns all active dependents with
        pending_allocation_since set.  Bypasses per-user ownership
        scoping, intended for the daily reminder job only."""
        return frappe.get_all(
            "Dependent",
            filters={
                "is_active": 1,
                "pending_allocation_since": ["is", "set"],
            },
            fields=[
                "name", "dependent_name", "guardian",
                "total_savings", "pending_allocation_since",
                "last_allocation_reminder_on",
            ],
        )

    @staticmethod
    def _clear_pending_allocation_on_dependent(dependent_name: str) -> None:
        dep = frappe.get_doc("Dependent", dependent_name, ignore_permissions=True)
        if dep.get("pending_allocation_since"):
            dep.pending_allocation_since = None
            dep.last_allocation_reminder_on = None
            dep.save(ignore_permissions=True)

    @staticmethod
    def try_claim_pending_allocation_reminder(dependent_name: str) -> bool:
        """Check if a pending-allocation reminder can be sent today
        and mark it as sent.  Returns True if the caller should send
        the message, False if already sent today or not pending."""
        dep = frappe.get_doc("Dependent", dependent_name, ignore_permissions=True)
        if not dep.get("pending_allocation_since"):
            return False
        if dep.get("last_allocation_reminder_on") and \
           getdate(dep.last_allocation_reminder_on) == getdate(frappe_today()):
            return False
        dep.last_allocation_reminder_on = frappe_today()
        dep.save(ignore_permissions=True)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_allocation(
        guardian: str,
        allocation: str,
    ) -> Document:
        try:
            doc = frappe.get_doc("Pocket Money Allocation", allocation, ignore_permissions=True)
        except frappe.DoesNotExistError as exc:
            raise PocketMoneyAllocationNotFoundError(
                _("Pocket money allocation not found.")
            ) from exc

        try:
            DependentService.get_dependent(guardian, doc.dependent)
        except DependentNotFoundError as exc:
            # Allocation exists, but does not belong to this guardian —
            # report as not-found rather than leaking existence.
            raise PocketMoneyAllocationNotFoundError(
                _("Pocket money allocation not found.")
            ) from exc

        return doc

    @staticmethod
    def _get_active_allocation_for_dependent(
        dependent: str,
    ) -> Optional[Document]:
        name = frappe.db.get_value(
            "Pocket Money Allocation",
            {
                "dependent": dependent,
                "is_active": 1,
            },
            "name",
        )

        if not name:
            return None

        return frappe.get_doc("Pocket Money Allocation", name, ignore_permissions=True)

    @staticmethod
    def _guardian_dependent_names(guardian: str) -> list[str]:
        return frappe.get_all(
            "Dependent",
            filters={"guardian": guardian},
            pluck="name",
        )

    @staticmethod
    def _calculate_spent_amount(
        owner_user: str,
        dependent: str,
        start_date,
        end_date,
    ) -> float:
        total = frappe.db.sql(
            """SELECT SUM(amount) FROM `tabExpense`
            WHERE owner_user = %s AND dependent = %s
            AND expense_date BETWEEN %s AND %s""",
            (owner_user, dependent, start_date, end_date),
        )

        return flt(total[0][0] if total and total[0][0] else 0)

    @staticmethod
    def get_period_end_date(allocation_date, allocation_period: str):
        start = getdate(allocation_date)

        if allocation_period == AllocationPeriod.WEEKLY:
            return add_days(start, 6)

        if allocation_period == AllocationPeriod.MONTHLY:
            return add_days(add_months(start, 1), -1)

        if allocation_period == AllocationPeriod.QUARTERLY:
            return add_days(add_months(start, 3), -1)

        if allocation_period == AllocationPeriod.YEARLY:
            return add_days(add_months(start, 12), -1)

        return start

    @staticmethod
    def _set_active_status(
        guardian: str,
        allocation: str,
        is_active: bool,
    ) -> Document:
        doc = PocketMoneyService._get_allocation(guardian, allocation)

        if doc.is_active == is_active:
            return doc

        doc.is_active = is_active
        doc.save(ignore_permissions=True)

        logger.info(
            "Pocket money allocation %s | guardian=%s | id=%s",
            "restored" if is_active else "archived",
            guardian,
            doc.name,
        )

        return doc

    @staticmethod
    def _validate_dependent(
        guardian: str,
        dependent: str,
    ) -> None:
        DependentService.get_dependent(guardian, dependent)

    @staticmethod
    def _validate_period(allocation_period: str) -> None:
        valid_periods = {item.value for item in AllocationPeriod}

        if allocation_period not in valid_periods:
            raise InvalidAllocationPeriodError(
                _("Invalid allocation period '{0}'.").format(allocation_period)
            )

    @staticmethod
    def _validate_amount(amount: float) -> float:
        if amount is None:
            raise InvalidAllocationAmountError(
                _("Allocated amount is required.")
            )

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidAllocationAmountError(
                _("Allocated amount must be numeric.")
            )

        if amount < 0:
            raise InvalidAllocationAmountError(
                _("Allocated amount must not be negative.")
            )

        return amount

    @staticmethod
    def _validate_carry_forward(amount: float) -> float:
        if amount is None:
            return 0.0

        try:
            amount = float(amount)
        except (TypeError, ValueError):
            raise InvalidCarryForwardAmountError(
                _("Carry forward amount must be numeric.")
            )

        if amount < 0:
            raise InvalidCarryForwardAmountError(
                _("Carry forward amount cannot be negative.")
            )

        return amount

    @staticmethod
    def _validate_dates(allocation_date) -> None:
        try:
            getdate(allocation_date)
        except Exception as exc:
            raise InvalidAllocationDateError(
                _("Allocation date is invalid.")
            ) from exc

    @staticmethod
    def _validate_delete(allocation: Document) -> None:
        # No other DocType links to Pocket Money Allocation, so there
        # is nothing to guard against before deletion.
        return None

    @staticmethod
    def rollover_allocation(
        guardian: str,
        dependent: str,
    ) -> Document:
        PocketMoneyService._validate_dependent(guardian, dependent)

        current = PocketMoneyService._get_active_allocation_for_dependent(dependent)

        if current is None:
            raise PocketMoneyAllocationNotFoundError(
                _("No active pocket money allocation to roll over.")
            )

        balance = PocketMoneyService.get_balance(guardian, dependent)
        remaining = balance["remaining_amount"] if balance else 0.0

        current.is_active = 0
        current.save(ignore_permissions=True)

        dependent_doc = DependentService.get_dependent(guardian, dependent)
        needs_save = False

        # Unused balance rolls into the dependent's savings ledger on the
        # Dependent doc (roadmap phase 24), separate from the spendable
        # allocation. When carry-forward is disabled the unused amount is
        # forfeited instead of being added to savings.
        if remaining > 0 and dependent_doc.get("allow_carry_forward", True):
            dependent_doc.total_savings = (
                flt(dependent_doc.get("total_savings", 0)) + remaining
            )
            needs_save = True

        if not dependent_doc.get("pending_allocation_since"):
            dependent_doc.pending_allocation_since = frappe_today()
            needs_save = True
        if needs_save:
            dependent_doc.save(ignore_permissions=True)

        new_allocation = PocketMoneyService.create_allocation(
            guardian=guardian,
            dependent=dependent,
            allocated_amount=0.0,
            allocation_period=current.allocation_period,
            allocation_date=frappe_today(),
            carry_forward_amount=0.0,
            remarks=_("Rolled over from previous period"),
        )
        logger.info(
            "Pocket money rolled over | guardian=%s | dependent=%s | old_id=%s | new_id=%s | savings_added=%s",
            guardian, dependent, current.name, new_allocation.name, remaining,
        )
        return new_allocation