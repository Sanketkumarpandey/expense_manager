# Copyright (c) 2026, Sanket Kumar and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class Category(Document):
    def before_validate(self):
        self.normalize_fields()

    def validate(self):
        self.validate_category_name()
        self.validate_duplicate_category()
        self.validate_icon()

    def normalize_fields(self):
        if self.category_name:
            self.category_name = self.category_name.strip()

        if self.icon:
            self.icon = self.icon.strip()

    def validate_category_name(self):
        if not self.category_name:
            frappe.throw(_("Category Name is required."))

        if not self.category_name.strip():
            frappe.throw(_("Category Name cannot be empty."))

    def validate_duplicate_category(self):
        existing_categories = frappe.get_all(
            "Category",
            filters={"name": ["!=", self.name], "owner_user": self.owner_user},
            fields=["name", "category_name"],
        )

        for category in existing_categories:
            if (
                category.category_name
                and category.category_name.casefold()
                == self.category_name.casefold()
            ):
                frappe.throw(
                    _("Category '{0}' already exists.").format(
                        category.category_name
                    )
                )

    def validate_icon(self):
        if self.icon and len(self.icon) > 50:
            frappe.throw(_("Icon cannot exceed 50 characters."))