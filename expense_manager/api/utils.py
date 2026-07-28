"""Shared helpers for the REST API layer."""

import frappe


def current_user() -> str:
    """Return the authenticated Frappe session user or abort with 401."""
    user = frappe.session.user
    if user == "Guest":
        frappe.throw("You must be logged in.")
    return user
