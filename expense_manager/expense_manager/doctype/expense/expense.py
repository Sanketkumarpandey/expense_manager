# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Expense(Document):
    def before_validate(self):
        self.normalize_fields()

    def validate(self):
        self.validate_required_fields()
        self.validate_amount()
        self.validate_expense_date()
        self.validate_description()
        self.validate_voice_transcript()

    def normalize_fields(self):
        if self.owner_user:
            self.owner_user = self.owner_user.strip()

        if self.description:
            self.description = self.description.strip()

        if self.voice_transcript:
            self.voice_transcript = self.voice_transcript.strip()

    def validate_required_fields(self):
        if not self.owner_user:
            frappe.throw(_("Owner User is required."))

        if not self.category:
            frappe.throw(_("Category is required."))

        if self.amount is None:
            frappe.throw(_("Amount is required."))

        if not self.expense_date:
            frappe.throw(_("Expense Date is required."))

    def validate_amount(self):
        if self.amount <= 0:
            frappe.throw(_("Amount must be greater than zero."))

    def validate_expense_date(self):
        if getdate(self.expense_date) > getdate(today()):
            frappe.throw(_("Expense Date cannot be in the future."))

    def validate_description(self):
        if self.description:
            if not self.description.strip():
                frappe.throw(_("Description cannot be empty."))

            if len(self.description) > 500:
                frappe.throw(_("Description cannot exceed 500 characters."))

    def validate_voice_transcript(self):
        if self.voice_transcript and len(self.voice_transcript) > 10000:
            frappe.throw(_("Voice Transcript cannot exceed 10000 characters."))