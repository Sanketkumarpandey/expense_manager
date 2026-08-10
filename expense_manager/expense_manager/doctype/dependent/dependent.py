# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Dependent(Document):
    def before_validate(self):
        self.normalize_fields()

    def validate(self):
        self.validate_required_fields()
        self.validate_dependent_name()
        self.validate_default_monthly_allowance()
        self.validate_telegram_username()
        self.validate_telegram_user_id()

    def normalize_fields(self):
        if self.dependent_name:
            self.dependent_name = self.dependent_name.strip()

        if self.telegram_username:
            self.telegram_username = self.telegram_username.strip().lstrip("@")

        if self.telegram_user_id:
            self.telegram_user_id = self.telegram_user_id.strip()

    def validate_required_fields(self):
        if not self.dependent_name:
            frappe.throw(_("Dependent Name is required."))

        if not self.guardian:
            frappe.throw(_("Guardian is required."))

        if not self.relationship:
            frappe.throw(_("Relationship is required."))

        if self.default_monthly_allowance is None:
            frappe.throw(_("Default Monthly Allowance is required."))

    def validate_dependent_name(self):
        if not self.dependent_name.strip():
            frappe.throw(_("Dependent Name cannot be empty."))

        existing = frappe.db.exists(
            "Dependent",
            {
                "dependent_name": self.dependent_name,
                "guardian": self.guardian,
                "name": ["!=", self.name],
            },
        )

        if existing:
            frappe.throw(_("Dependent Name already exists."))

    def validate_default_monthly_allowance(self):
        if self.default_monthly_allowance < 0:
            frappe.throw(
                _("Default Monthly Allowance cannot be negative.")
            )

    def validate_telegram_username(self):
        if self.telegram_username:
            if " " in self.telegram_username:
                frappe.throw(
                    _("Telegram Username cannot contain spaces.")
                )

            if len(self.telegram_username) > 32:
                frappe.throw(
                    _("Telegram Username cannot exceed 32 characters.")
                )

    def validate_telegram_user_id(self):
        if self.telegram_user_id:
            if not self.telegram_user_id.isdigit():
                frappe.throw(
                    _("Telegram User ID must contain only digits.")
                )

            existing_dependent = frappe.db.exists(
                "Dependent",
                {
                    "telegram_user_id": self.telegram_user_id,
                    "name": ["!=", self.name],
                },
            )

            if existing_dependent:
                frappe.throw(
                    _("Telegram User ID already assigned to another dependent.")
                )

            existing_link = frappe.db.exists(
                "Telegram Link",
                {
                    "telegram_user_id": self.telegram_user_id,
                    "is_active": 1,
                },
            )

            if existing_link:
                frappe.throw(
                    _("Telegram User ID already linked to a user account.")
                )
