import frappe

from expense_manager.services.category_service import CategoryService

GUARDIAN_ROLE = "Expense Manager User"


def user_on_update(doc, method=None):
    """Seed default categories when a user is assigned the Expense Manager User role.

    Uses User.on_update to catch both:
    - New user creation with the role pre-assigned
    - Later role assignment to an existing user

    Idempotent: create_default_categories skips existing categories.
    """
    if GUARDIAN_ROLE not in frappe.get_roles(doc.name):
        return

    CategoryService.create_default_categories(doc.name)
