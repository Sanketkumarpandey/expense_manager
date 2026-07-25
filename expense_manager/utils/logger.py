import frappe

logger = frappe.logger(
    "expense_manager",
    allow_site=True,
    file_count=10,
)