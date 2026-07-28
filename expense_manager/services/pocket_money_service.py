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

        remaining_amount = (
            allocation.allocated_amount + allocation.carry_forward_amount - spent_amount
        )

        return {
            "allocation": allocation.name,
            "allocated_amount": allocation.allocated_amount,
            "spent_amount": spent_amount,
            "carry_forward": allocation.carry_forward_amount,
            "remaining_amount": remaining_amount,
            "available_amount": remaining_amount,
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

        remaining_amount = (
            allocation.allocated_amount + allocation.carry_forward_amount - spent_amount
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
        total = frappe.db.get_value(
            "Expense",
            {
                "owner_user": owner_user,
                "dependent": dependent,
                "expense_date": ["between", [start_date, end_date]],
            },
            "sum(amount)",
        )

        return flt(total)

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

        if amount <= 0:
            raise InvalidAllocationAmountError(
                _("Allocated amount must be greater than zero.")
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

        dependent_doc = DependentService.get_dependent(guardian, dependent)
        balance = PocketMoneyService.get_balance(guardian, dependent)
        remaining = balance["remaining_amount"] if balance else 0.0
        carry_forward = remaining if dependent_doc.allow_carry_forward and remaining > 0 else 0.0

        current.is_active = 0
        current.save(ignore_permissions=True)

        new_allocation = PocketMoneyService.create_allocation(
            guardian=guardian,
            dependent=dependent,
            allocated_amount=dependent_doc.default_monthly_allowance,
            allocation_period=current.allocation_period,
            allocation_date=frappe_today(),
            carry_forward_amount=carry_forward,
            remarks=_("Rolled over from previous period"),
        )

        logger.info(
            "Pocket money rolled over | guardian=%s | dependent=%s | old_id=%s | new_id=%s | carried_forward=%s",
            guardian, dependent, current.name, new_allocation.name, carry_forward,
        )

        return new_allocation