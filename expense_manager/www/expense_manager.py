import frappe

no_cache = 1


def get_context(context):
    context.boot = {
        "user": frappe.session.user,
        "lang": frappe.local.lang,
    }
    if frappe.session.user != "Guest":
        context.boot["csrf_token"] = frappe.sessions.get_csrf_token()
    return context
