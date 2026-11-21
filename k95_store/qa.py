import frappe


def smoke():
	doctypes = [
		"Store Settings",
		"Gate Entry",
		"Gate Entry Photo",
		"Gate Entry Checklist Run",
		"Batch Format Rule",
		"Store Putaway",
		"Store Putaway Item",
		"Store Stock Reservation",
		"Store Issue",
		"Store Issue Item",
		"Production Issue Request",
		"Production Issue Request Item",
		"Labelling Material Request",
		"Labelling Material Request Item",
		"Store Stock Return",
		"Store Stock Return Item",
		"Store Vendor Return",
		"Store Vendor Return Item",
		"Store Damage Report",
		"Store Opening Stock",
		"Store Transfer",
		"Store Cycle Count",
		"Store Cycle Count Item",
		"Store Adjustment",
		"Store Stock Reconciliation Log",
		"Store GRN Charge",
		"Store Invoice Image",
		"Store Debit Note",
		"Store Debit Note Item",
		"AI Model Key",
	]
	missing = [name for name in doctypes if not frappe.db.exists("DocType", name)]
	roles_missing = [role for role in ("Gate Security", "Store User", "Store Manager", "Store Auditor", "Production Requester", "Labelling Requester") if not frappe.db.exists("Role", role)]
	item_fields = ["custom_store_item", "custom_mfg_date_required", "custom_allow_auto_generate", "custom_qc_required"]
	wh_fields = ["custom_location_code", "custom_location_type", "custom_rack"]
	batch_fields = ["custom_supplier_batch", "custom_lot_status", "custom_is_opening_lot", "custom_grn"]
	pr_fields = ["custom_gate_entry", "custom_arrival_type", "custom_po_bypass", "custom_freight_option"]
	gate_fields = ["arrival_type"]
	missing_fields = []
	for dt, fields in (
		("Item", item_fields),
		("Warehouse", wh_fields),
		("Batch", batch_fields),
		("Purchase Receipt", pr_fields),
		("Gate Entry", gate_fields),
	):
		meta = frappe.get_meta(dt)
		for fieldname in fields:
			if not meta.has_field(fieldname):
				missing_fields.append(f"{dt}.{fieldname}")
	return {
		"missing_doctypes": missing,
		"missing_roles": roles_missing,
		"missing_fields": missing_fields,
		"store_settings": bool(frappe.db.exists("DocType", "Store Settings")),
		"ok": not missing and not roles_missing and not missing_fields,
	}
