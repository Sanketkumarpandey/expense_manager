"""Whitelisted Pocket Money endpoints. Thin wrappers only — every
rule lives in PocketMoneyService. Scoped to frappe.session.user (the
guardian) — "guardian" and "owner_user" are the same value throughout
this file, matching PocketMoneyService's own parameter naming."""

import frappe
from frappe.utils import cint, flt

from expense_manager.api.utils import current_user as _current_user
from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.pocket_money_service import PocketMoneyService

# Same rationale as api/budgets.py: PocketMoneyService.update_allocation
# distinguishes "remarks not supplied" from "remarks explicitly
# cleared" via its own private _UNSET. This local sentinel preserves
# that without importing the private one.
_API_UNSET = "__unset__"


@frappe.whitelist(methods=["POST"])
def create_allocation(
	dependent: str,
	allocated_amount: float,
	allocation_period: str,
	allocation_date: str | None = None,
	carry_forward_amount: float = 0,
	remarks: str | None = None,
):
	guardian = _current_user()
	try:
		return PocketMoneyService.create_allocation(
			guardian,
			dependent,
			flt(allocated_amount),
			allocation_period,
			allocation_date=allocation_date,
			carry_forward_amount=flt(carry_forward_amount),
			remarks=remarks,
		).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_allocation(allocation: str):
	guardian = _current_user()
	try:
		return PocketMoneyService.get_allocation(guardian, allocation).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def update_allocation(
	allocation: str,
	allocated_amount: float | None = None,
	allocation_period: str | None = None,
	allocation_date: str | None = None,
	carry_forward_amount: float | None = None,
	remarks: str | None = _API_UNSET,
):
	guardian = _current_user()

	kwargs = {}
	if allocated_amount is not None:
		kwargs["allocated_amount"] = flt(allocated_amount)
	if allocation_period is not None:
		kwargs["allocation_period"] = allocation_period
	if allocation_date is not None:
		kwargs["allocation_date"] = allocation_date
	if carry_forward_amount is not None:
		kwargs["carry_forward_amount"] = flt(carry_forward_amount)
	if remarks is not _API_UNSET:
		kwargs["remarks"] = remarks or None

	try:
		return PocketMoneyService.update_allocation(guardian, allocation, **kwargs).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def delete_allocation(allocation: str):
	guardian = _current_user()
	try:
		PocketMoneyService.delete_allocation(guardian, allocation)
		return {"success": True}
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def archive_allocation(allocation: str):
	guardian = _current_user()
	try:
		return PocketMoneyService.archive_allocation(guardian, allocation).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["POST"])
def restore_allocation(allocation: str):
	guardian = _current_user()
	try:
		return PocketMoneyService.restore_allocation(guardian, allocation).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def list_allocations(dependent: str | None = None, active_only: int = 0):
	guardian = _current_user()
	try:
		return PocketMoneyService.list_allocations(
			guardian,
			dependent=dependent,
			active_only=bool(cint(active_only)),
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def search_allocations(search_text: str | None = None, active_only: int = 1):
	guardian = _current_user()
	try:
		return PocketMoneyService.search_allocations(
			guardian,
			search_text,
			active_only=bool(cint(active_only)),
		)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}


@frappe.whitelist(methods=["GET"])
def get_balance(dependent: str | None = None):
	if not dependent:
		dependent = frappe.form_dict.get("dependent") or (
			frappe.request and frappe.request.args.get("dependent")
		)
	guardian = _current_user()
	try:
		balance = PocketMoneyService.get_balance(guardian, dependent)
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}

	if balance is None:
		return {"success": False, "message": "No active pocket money allocation for this dependent."}

	return balance


@frappe.whitelist(methods=["POST"])
def rollover_allocation(dependent: str):
	"""
	Manual, desk-triggered rollover for a single dependent — e.g. a
	guardian who doesn't want to wait for the scheduled monthly
	rollover job. Same underlying method the job itself calls.
	"""
	guardian = _current_user()
	try:
		return PocketMoneyService.rollover_allocation(guardian, dependent).as_dict()
	except ExpenseManagerError as exc:
		return {"success": False, "message": str(exc)}
