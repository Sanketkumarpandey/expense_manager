from __future__ import annotations

import frappe
from frappe.utils import getdate, today

from expense_manager.services.exceptions import ExpenseManagerError
from expense_manager.services.pocket_money_service import PocketMoneyService
from expense_manager.utils.logger import logger


def run_monthly_rollover() -> None:
	"""
	Scheduled entry point. Despite the name, this runs against every
	active Pocket Money Allocation regardless of period (weekly,
	monthly, quarterly, yearly) — it just rolls over whichever ones
	have actually reached their period end as of today. Meant to be
	hooked under scheduler_events["daily"], not ["monthly"], so a
	weekly allocation doesn't sit un-rolled for weeks waiting for a
	monthly-only cron.

	This function owns enumeration only — finding which allocations
	exist and whether their period has ended. The actual rollover
	(archive + create next + carry forward) stays entirely inside
	PocketMoneyService.rollover_allocation(), same as every other job
	in this app defers to its domain service rather than reimplementing
	business rules.
	"""
	cutoff = getdate(today())

	allocations = frappe.get_all(
		"Pocket Money Allocation",
		filters={"is_active": 1},
		fields=["name", "dependent", "allocation_date", "allocation_period"],
	)

	rolled_over = 0
	skipped = 0
	failed = 0

	for allocation in allocations:
		period_end = PocketMoneyService.get_period_end_date(
			allocation["allocation_date"],
			allocation["allocation_period"],
		)

		if cutoff <= period_end:
			skipped += 1
			continue

		guardian = frappe.db.get_value("Dependent", allocation["dependent"], "guardian")

		if not guardian:
			logger.info(
				"Monthly rollover skipped | allocation=%s | dependent=%s | reason=no guardian on dependent",
				allocation["name"],
				allocation["dependent"],
			)
			skipped += 1
			continue

		try:
			PocketMoneyService.rollover_allocation(guardian, allocation["dependent"])
			frappe.db.commit()
			rolled_over += 1
		except ExpenseManagerError as exc:
			frappe.db.rollback()
			failed += 1
			logger.info(
				"Monthly rollover failed | allocation=%s | dependent=%s | guardian=%s | error=%s",
				allocation["name"],
				allocation["dependent"],
				guardian,
				str(exc),
			)

	logger.info(
		"Monthly rollover run complete | rolled_over=%s | skipped=%s | failed=%s",
		rolled_over,
		skipped,
		failed,
	)
