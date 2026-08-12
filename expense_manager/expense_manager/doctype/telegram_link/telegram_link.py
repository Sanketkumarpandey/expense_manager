# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TelegramLink(Document):
	def before_validate(self):
		self.normalize_fields()

	def validate(self):
		self.validate_required_fields()
		self.validate_telegram_user_id()
		self.validate_telegram_username()
		self.validate_language_code()
		self.validate_unique_user()
		self.validate_unique_telegram_user()

	def normalize_fields(self):
		if self.first_name:
			self.first_name = self.first_name.strip()

		if self.last_name:
			self.last_name = self.last_name.strip()

		if self.telegram_username:
			self.telegram_username = self.telegram_username.strip().lstrip("@")

		if self.language_code:
			self.language_code = self.language_code.strip().lower()

	def validate_required_fields(self):
		if not self.user:
			frappe.throw(_("User is required."))

		if not self.telegram_user_id:
			frappe.throw(_("Telegram User ID is required."))

		if not self.linked_on:
			frappe.throw(_("Linked On is required."))

	def validate_telegram_user_id(self):
		if not self.telegram_user_id.isdigit():
			frappe.throw(_("Telegram User ID must contain only digits."))

	def validate_telegram_username(self):
		if self.telegram_username:
			if " " in self.telegram_username:
				frappe.throw(_("Telegram Username cannot contain spaces."))

			if len(self.telegram_username) > 32:
				frappe.throw(_("Telegram Username cannot exceed 32 characters."))

	def validate_language_code(self):
		if self.language_code:
			if len(self.language_code) > 10:
				frappe.throw(_("Language Code cannot exceed 10 characters."))

	def validate_unique_user(self):
		existing = frappe.db.exists(
			"Telegram Link",
			{
				"user": self.user,
				"is_active": 1,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(_("This user is already linked to a Telegram account."))

	def validate_unique_telegram_user(self):
		existing = frappe.db.exists(
			"Telegram Link",
			{
				"telegram_user_id": self.telegram_user_id,
				"is_active": 1,
				"name": ["!=", self.name],
			},
		)

		if existing:
			frappe.throw(_("This Telegram account is already linked to another user."))
