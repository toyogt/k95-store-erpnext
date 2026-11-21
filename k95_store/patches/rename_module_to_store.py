import frappe


def execute():
	if frappe.db.exists("Module Def", "K95 Store"):
		if frappe.db.exists("Module Def", "Store"):
			frappe.db.sql(
				"update `tabDocType` set module=%s where module=%s",
				("Store", "K95 Store"),
			)
			frappe.db.sql(
				"update `tabReport` set module=%s where module=%s",
				("Store", "K95 Store"),
			)
			frappe.delete_doc("Module Def", "K95 Store", force=True, ignore_permissions=True)
		else:
			frappe.rename_doc("Module Def", "K95 Store", "Store", force=True)

	if frappe.db.exists("Workspace", "K95 Store") and not frappe.db.exists("Workspace", "Store"):
		frappe.rename_doc("Workspace", "K95 Store", "Store", force=True)
