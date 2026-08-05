import frappe
from expense_manager.services.category_service import CategoryService


def after_install():
    """Seed default categories for the Administrator user after app install."""
    admin_user = "Administrator"
    CategoryService.create_default_categories(admin_user)
