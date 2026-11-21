import frappe


EDIT_ROLES = {
	"Draft": [
		"Guard",
		"Factory Guard",
		"Gate Entry Editor",
		"Gate Security",
		"Store User",
		"Store Manager",
		"System Manager",
	],
	"Pending Verification": [
		"Guard",
		"Factory Guard",
		"Gate Entry Editor",
		"Gate Security",
		"Store User",
		"Store Manager",
		"System Manager",
	],
	"Submitted": [
		"Guard",
		"Factory Guard",
		"Gate Entry Editor",
		"Gate Security",
		"Store User",
		"Store Manager",
		"System Manager",
	],
	"Cancelled": ["Gate Entry Editor", "Store Manager", "System Manager"],
}

DOCSTATUS = {
	"Draft": "0",
	"Pending Verification": "0",
	"Submitted": "1",
	"Cancelled": "2",
}

STATE_STYLE = {
	"Draft": "Warning",
	"Pending Verification": "Info",
	"Submitted": "Success",
	"Cancelled": "Danger",
}

TRANSITIONS = [
	("Draft", "Send for Verification", "Pending Verification", "Guard"),
	("Draft", "Send for Verification", "Pending Verification", "Factory Guard"),
	("Draft", "Send for Verification", "Pending Verification", "Gate Entry Editor"),
	("Draft", "Send for Verification", "Pending Verification", "Gate Security"),
	("Draft", "Send for Verification", "Pending Verification", "Store User"),
	("Draft", "Send for Verification", "Pending Verification", "Store Manager"),
	("Draft", "Send for Verification", "Pending Verification", "System Manager"),
	("Pending Verification", "Send Back", "Draft", "Gate Entry Editor"),
	("Pending Verification", "Send Back", "Draft", "Store Manager"),
	("Pending Verification", "Send Back", "Draft", "System Manager"),
	("Pending Verification", "Submit", "Submitted", "Gate Entry Editor"),
	("Pending Verification", "Submit", "Submitted", "Store Manager"),
	("Pending Verification", "Submit", "Submitted", "System Manager"),
]


def ensure_gate_entry_workflow():
	if not frappe.db.exists("DocType", "Workflow"):
		return
	frappe.clear_cache(doctype="Gate Entry")
	for state, style in STATE_STYLE.items():
		_ensure_named("Workflow State", "workflow_state_name", state, {"style": style})
	for _state, action, _next, _role in TRANSITIONS:
		_ensure_named("Workflow Action Master", "workflow_action_name", action)

	workflow_name = "Gate Entry"
	if frappe.db.exists("Workflow", workflow_name):
		doc = frappe.get_doc("Workflow", workflow_name)
	else:
		doc = frappe.new_doc("Workflow")
		doc.workflow_name = workflow_name

	doc.document_type = "Gate Entry"
	doc.is_active = 1
	doc.override_status = 1
	doc.send_email_alert = 0
	doc.workflow_state_field = "workflow_state"
	doc.set("states", [])
	doc.set("transitions", [])
	for state, roles in EDIT_ROLES.items():
		for role in roles:
			if not frappe.db.exists("Role", role):
				continue
			doc.append(
				"states",
				{
					"state": state,
					"doc_status": DOCSTATUS[state],
					"allow_edit": role,
				},
			)
	for state, action, next_state, role in TRANSITIONS:
		if not frappe.db.exists("Role", role):
			continue
		doc.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": role,
				"allow_self_approval": 1,
			},
		)
	doc.save(ignore_permissions=True)


def _ensure_named(doctype, fieldname, value, extra=None):
	if frappe.db.exists(doctype, value):
		return
	data = {"doctype": doctype, fieldname: value}
	if extra:
		data.update(extra)
	frappe.get_doc(data).insert(ignore_permissions=True)
