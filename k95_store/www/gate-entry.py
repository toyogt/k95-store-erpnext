import frappe
from frappe import _


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.throw(_("Please login to create a gate entry."), frappe.PermissionError)
	context.no_cache = 1
	context.title = _("Gate Entry")
