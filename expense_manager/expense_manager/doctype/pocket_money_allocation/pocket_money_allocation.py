# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class PocketMoneyAllocation(Document):
	def before_validate(self):
		self.normalize_fields()

	def validate(self):
		self.validate_required_fields()
		self.validate_allocated_amount()
		self.validate_carry_forward_amount()
		self.validate_total_available_amount()
		self.validate_allocation_date()
		self.validate_duplicate_allocation()

	def normalize_fields(self):
		if self.remarks:
			self.remarks = self.remarks.strip()

		if self.carry_forward_amount is None:
			self.carry_forward_amount = 0

		if self.total_available_amount is None:
			self.total_available_amount = (self.allocated_amount or 0) + self.carry_forward_amount

	def validate_required_fields(self):
		if not self.dependent:
			frappe.throw(_("Dependent is required."))

		if self.allocated_amount is None:
			frappe.throw(_("Allocated Amount is required."))

		if not self.allocation_date:
			frappe.throw(_("Allocation Date is required."))

		if not self.allocation_period:
			frappe.throw(_("Allocation Period is required."))

	def validate_allocated_amount(self):
		# A zero-amount allocation is legal: it represents a rolled-over
		# period whose funds have not been assigned yet (pending
		# top-up, see PocketMoneyService.rollover_allocation).
		if self.allocated_amount < 0:
			frappe.throw(_("Allocated Amount cannot be negative."))

	def validate_carry_forward_amount(self):
		if self.carry_forward_amount < 0:
			frappe.throw(_("Carry Forward Amount cannot be negative."))

	def validate_total_available_amount(self):
		if not self.is_new():
			return
		expected_total = self.allocated_amount + self.carry_forward_amount
		if self.total_available_amount != expected_total:
			self.total_available_amount = expected_total

	def validate_allocation_date(self):
		if getdate(self.allocation_date) > getdate(today()):
			frappe.throw(_("Allocation Date cannot be in the future."))

	def validate_duplicate_allocation(self):
		if not self.is_active:
			return

		existing_allocations = frappe.get_all(
			"Pocket Money Allocation",
			filters={
				"name": ["!=", self.name],
				"dependent": self.dependent,
				"allocation_period": self.allocation_period,
				"is_active": 1,
			},
			fields=["allocation_date"],
		)

		for allocation in existing_allocations:
			if allocation.allocation_date == self.allocation_date:
				frappe.throw(
					_(
						"An active allocation already exists for this dependent on the selected date and period."
					)
				)
