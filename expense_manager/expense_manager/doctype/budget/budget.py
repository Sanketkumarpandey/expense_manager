import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class Budget(Document):
    def before_validate(self):
        self.normalize_fields()

    def validate(self):
        self.validate_required_fields()
        self.validate_allocated_amount()
        self.validate_spent_amount()
        self.validate_alert_threshold()
        self.validate_dates()
        self.validate_duplicate_budget()

    def normalize_fields(self):
        if self.owner_user:
            self.owner_user = self.owner_user.strip()

        if self.category:
            self.category = self.category.strip()

        if self.notes:
            self.notes = self.notes.strip()

        if hasattr(self, "dependent") and self.dependent:
            self.dependent = self.dependent.strip()

    def validate_required_fields(self):
        if not self.owner_user:
            frappe.throw(_("Owner User is required."))

        if not self.category:
            frappe.throw(_("Category is required."))

        if self.allocated_amount is None:
            frappe.throw(_("Allocated Amount is required."))

        if self.spent_amount is None:
            self.spent_amount = 0

        if not self.period:
            frappe.throw(_("Period is required."))

        if not self.start_date:
            frappe.throw(_("Start Date is required."))

        if not self.end_date:
            frappe.throw(_("End Date is required."))

    def validate_allocated_amount(self):
        if self.allocated_amount is not None and self.allocated_amount <= 0:
            frappe.throw(_("Allocated Amount must be greater than zero."))

    def validate_spent_amount(self):
        if self.spent_amount is not None and self.spent_amount < 0:
            frappe.throw(_("Spent Amount cannot be negative."))

    def validate_alert_threshold(self):
        if not 1 <= self.alert_threshold_pct <= 100:
            frappe.throw(_("Alert Threshold % must be between 1 and 100."))

    def validate_dates(self):
        if getdate(self.start_date) > getdate(self.end_date):
            frappe.throw(_("Start Date cannot be after End Date."))

    def validate_duplicate_budget(self):
        filters = {
            "name": ["!=", self.name],
            "owner_user": self.owner_user,
            "category": self.category,
            "period": self.period,
            "is_active": 1,
        }
        if self.dependent:
            filters["dependent"] = self.dependent
        else:
            filters["dependent"] = ["is", "not set"]

        existing_budgets = frappe.get_all(
            "Budget",
            filters=filters,
            fields=["name", "start_date", "end_date"],
        )

        for budget in existing_budgets:
            if (
                self.start_date <= budget.end_date
                and self.end_date >= budget.start_date
            ):
                frappe.throw(
                    _(
                        "An active budget already exists for this category during the selected period."
                    )
                )