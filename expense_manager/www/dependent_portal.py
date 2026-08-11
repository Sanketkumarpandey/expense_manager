import frappe

from expense_manager.api.dependents import get_portal_data

no_cache = 1


def get_context(context):
	token = getattr(context, "token", None) or frappe.form_dict.get("token")
	if not token:
		path = (frappe.local.request.path or "").strip("/").split("/")
		if len(path) >= 2 and path[0] == "dependent":
			token = path[1]

	context.token = token
	if token:
		res = get_portal_data(token=token)
		if res.get("success"):
			context.found = True
			context.portal_data = res
		else:
			context.found = False
			context.error_message = res.get("message")
	else:
		context.found = False
		context.error_message = "No dependent access token provided."

	return context
