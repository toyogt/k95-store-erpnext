"""One-shot helper used while scaffolding the app. Safe to keep."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "k95_store" / "doctype"
MODULE = "K95 Store"


def field(fieldname, label, fieldtype, **kwargs):
	data = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label}
	data.update(kwargs)
	return data


def perms(submit=False, extra=None):
	rows = [
		{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1, "email": 1},
		{"role": "Store Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1, "share": 1, "print": 1},
		{"role": "Store User", "read": 1, "write": 1, "create": 1, "report": 1, "export": 1, "print": 1},
		{"role": "Store Auditor", "read": 1, "report": 1, "export": 1, "print": 1},
	]
	if submit:
		for row in rows:
			if row["role"] in ("System Manager", "Store Manager", "Store User"):
				row["submit"] = 1
			if row["role"] in ("System Manager", "Store Manager"):
				row["cancel"] = 1
				row["amend"] = 1
	for role, flags in extra or []:
		row = {"role": role, "read": 1}
		row.update(flags)
		rows.append(row)
	return rows


def doctype(name, fields, **kwargs):
	field_order = [f["fieldname"] for f in fields]
	doc = {
		"actions": [],
		"creation": "2026-11-05 00:00:00.000000",
		"doctype": "DocType",
		"engine": "InnoDB",
		"field_order": field_order,
		"fields": fields,
		"index_web_pages_for_search": 1,
		"links": [],
		"modified": "2026-11-05 00:00:00.000000",
		"modified_by": "Administrator",
		"module": MODULE,
		"name": name,
		"owner": "Administrator",
		"permissions": kwargs.pop("permissions", perms()),
		"sort_field": "modified",
		"sort_order": "DESC",
		"states": [],
		"track_changes": 1,
	}
	doc.update(kwargs)
	return doc


def write_doctype(name, doc, controller):
	slug = name.lower().replace(" ", "_")
	folder = ROOT / slug
	folder.mkdir(parents=True, exist_ok=True)
	(folder / "__init__.py").write_text("")
	(folder / f"{slug}.json").write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
	py = folder / f"{slug}.py"
	if not py.exists():
		py.write_text(controller, encoding="utf-8")


def ctrl(class_name, body="\tpass\n"):
	return (
		"from frappe.model.document import Document\n\n\n"
		f"class {class_name}(Document):\n{body}"
	)


def child(name, fields):
	return doctype(
		name,
		fields,
		istable=1,
		editable_grid=1,
		permissions=[],
		track_changes=0,
	)


def build():
	write_doctype(
		"Store Settings",
		doctype(
			"Store Settings",
			[
				field("company", "Company", "Link", options="Company", reqd=1),
				field("warehouses_section", "Warehouses", "Section Break"),
				field("stores_group_warehouse", "Stores Group", "Link", options="Warehouse"),
				field("receiving_warehouse", "Receiving Warehouse", "Link", options="Warehouse"),
				field("rejected_warehouse", "Rejected Warehouse", "Link", options="Warehouse"),
				field("quarantine_warehouse", "Quarantine Warehouse", "Link", options="Warehouse"),
				field("rules_section", "Rules", "Section Break"),
				field("enable_strict_supplier_item_mapping", "Strict Supplier Item Mapping", "Check", default="1"),
				field("auto_approve_return_percent", "Auto Approve Return Percent", "Float", default="5"),
				field("auto_approve_return_qty", "Auto Approve Return Qty", "Float", default="2"),
				field("float_epsilon", "Float Epsilon", "Float", default="0.0001"),
				field("landed_cost_account", "Landed Cost Account", "Link", options="Account"),
			],
			issingle=1,
			permissions=perms(),
		),
		ctrl("StoreSettings"),
	)

	write_doctype(
		"Gate Entry Photo",
		child(
			"Gate Entry Photo",
			[
				field("slot", "Slot", "Select", options="vehicle\ninvoice\nmaterial", in_list_view=1, reqd=1),
				field("image", "Image", "Attach Image", in_list_view=1, reqd=1),
				field("source", "Source", "Select", options="camera\nfile", default="camera", in_list_view=1),
			],
		),
		ctrl("GateEntryPhoto"),
	)

	write_doctype(
		"Gate Entry",
		doctype(
			"Gate Entry",
			[
				field("naming_series", "Series", "Select", options="GE-.YYYY.-.#####", default="GE-.YYYY.-.#####", hidden=1),
				field("arrived_at", "Arrived At", "Datetime", reqd=1, in_list_view=1),
				field("status", "Status", "Select", options="OPEN\nCLOSED", default="OPEN", reqd=1, in_list_view=1, in_standard_filter=1),
				field("transport_type", "Transport Type", "Select", options="vehicle\ncourier\non_foot", default="vehicle", reqd=1),
				field("vehicle_number", "Vehicle Number", "Data"),
				field("col_break_1", "", "Column Break"),
				field("driver_name", "Driver Name", "Data"),
				field("driver_number", "Driver Mobile", "Data", reqd=1),
				field("supplier_name", "Party Name", "Data"),
				field("notes", "Notes", "Small Text"),
				field("photos_section", "Photos", "Section Break"),
				field("vehicle_photo", "Vehicle Photo", "Attach Image"),
				field("invoice_photo", "Invoice Photo", "Attach Image"),
				field("material_photo", "Material Photo", "Attach Image"),
				field("photos", "Extra Photos", "Table", options="Gate Entry Photo"),
				field("meta_section", "Audit", "Section Break"),
				field("submitted_by_name", "Submitted By", "Data", read_only=1),
				field("submitted_by_email", "Submitted By Email", "Data", read_only=1),
				field("checklist_run", "Checklist Run", "Link", options="Gate Entry Checklist Run", read_only=1),
			],
			autoname="GE-.YYYY.-.#####",
			is_submittable=0,
			search_fields="vehicle_number,supplier_name,status",
			title_field="vehicle_number",
			permissions=perms(extra=[("Gate Security", {"create": 1, "write": 1, "print": 1})]),
		),
		ctrl("GateEntry"),
	)

	write_doctype(
		"Gate Entry Checklist Run",
		doctype(
			"Gate Entry Checklist Run",
			[
				field("gate_entry", "Gate Entry", "Link", options="Gate Entry", reqd=1, in_list_view=1),
				field("completed_by", "Completed By", "Data"),
				field("completed_at", "Completed At", "Datetime"),
				field("remarks", "Remarks", "Small Text"),
			],
			autoname="CLR-.#####",
			permissions=perms(extra=[("Gate Security", {"create": 1, "write": 1})]),
		),
		ctrl("GateEntryChecklistRun"),
	)

	write_doctype(
		"Batch Format Rule",
		doctype(
			"Batch Format Rule",
			[
				field("rule_name", "Rule Name", "Data", reqd=1),
				field("batch_date_source", "Date Source", "Select", options="MFG_START\nLABEL_START", default="MFG_START"),
				field("seq_source", "Sequence Source", "Select", options="COUNTER\nSERIAL_CHAMBER", default="COUNTER"),
				field("reset_scope", "Reset Scope", "Select", options="DAILY\nMONTHLY\nYEARLY\nNEVER", default="DAILY"),
				field("format_json", "Format JSON", "Code", options="JSON"),
				field("is_active", "Active", "Check", default="1"),
			],
			autoname="BR-.######",
			permissions=perms(),
		),
		ctrl("BatchFormatRule"),
	)

	write_doctype(
		"Store Putaway Item",
		child(
			"Store Putaway Item",
			[
				field("lot_id", "Lot", "Link", options="Batch", in_list_view=1, reqd=1),
				field("item_code", "Item", "Link", options="Item", in_list_view=1, read_only=1),
				field("location", "Location", "Link", options="Warehouse", in_list_view=1, reqd=1),
				field("location_code", "Location Code", "Data", read_only=1),
				field("quantity", "Quantity", "Float", in_list_view=1, reqd=1),
				field("notes", "Notes", "Data"),
			],
		),
		ctrl("StorePutawayItem"),
	)

	write_doctype(
		"Store Putaway",
		doctype(
			"Store Putaway",
			[
				field("putaway_at", "Putaway At", "Datetime"),
				field("putaway_by", "Putaway By", "Link", options="User", default="__user"),
				field("status", "Status", "Select", options="draft\nposted", default="draft", read_only=1),
				field("stock_entry", "Stock Entry", "Link", options="Stock Entry", read_only=1),
				field("items", "Items", "Table", options="Store Putaway Item", reqd=1),
			],
			autoname="PUT-.YYYY.MM.DD.-.####",
			is_submittable=1,
			permissions=perms(submit=True),
		),
		ctrl("StorePutaway"),
	)

	write_doctype(
		"Store Stock Reservation",
		doctype(
			"Store Stock Reservation",
			[
				field("reference_doctype", "Reference Type", "Link", options="DocType"),
				field("reference_number", "Reference Number", "Dynamic Link", options="reference_doctype", in_list_view=1),
				field("request_line_id", "Request Line", "Data"),
				field("item_code", "Item", "Link", options="Item", reqd=1, in_list_view=1),
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("location", "Location", "Link", options="Warehouse", reqd=1),
				field("location_code", "Location Code", "Data"),
				field("quantity", "Quantity", "Float", reqd=1, in_list_view=1),
				field("uom", "UOM", "Link", options="UOM"),
				field("status", "Status", "Select", options="ACTIVE\nCONSUMED\nRELEASED", default="ACTIVE", reqd=1, in_standard_filter=1),
				field("reserved_at", "Reserved At", "Datetime"),
			],
			autoname="RSV-.#####",
			permissions=perms(),
		),
		ctrl("StoreStockReservation"),
	)

	write_doctype(
		"Store Issue Item",
		child(
			"Store Issue Item",
			[
				field("item_code", "Item", "Link", options="Item", in_list_view=1),
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("location", "Location", "Link", options="Warehouse", reqd=1, in_list_view=1),
				field("location_code", "Location Code", "Data"),
				field("requested_quantity", "Requested Qty", "Float"),
				field("issued_quantity", "Issued Qty", "Float", reqd=1, in_list_view=1),
				field("returned_quantity", "Returned Qty", "Float", default="0", read_only=1),
				field("reservation", "Reservation", "Link", options="Store Stock Reservation"),
			],
		),
		ctrl("StoreIssueItem"),
	)

	write_doctype(
		"Store Issue",
		doctype(
			"Store Issue",
			[
				field("issue_type", "Issue Type", "Select", options="production\ndispatch\ninternal", default="production", reqd=1, in_list_view=1),
				field("reference_doctype", "Reference Type", "Link", options="DocType"),
				field("reference_number", "Reference Number", "Dynamic Link", options="reference_doctype", in_list_view=1),
				field("status", "Status", "Select", options="confirmed\ncancelled", default="confirmed", read_only=1),
				field("return_status", "Return Status", "Select", options="none\npartial\nfull", default="none", read_only=1),
				field("issued_by", "Issued By", "Link", options="User", read_only=1),
				field("issued_at", "Issued At", "Datetime", read_only=1),
				field("stock_entry", "Stock Entry", "Link", options="Stock Entry", read_only=1),
				field("notes", "Notes", "Small Text"),
				field("items", "Items", "Table", options="Store Issue Item", reqd=1),
			],
			autoname="ISS-.YYYY.MM.DD.-.####",
			is_submittable=1,
			permissions=perms(submit=True),
		),
		ctrl("StoreIssue"),
	)

	write_doctype(
		"Production Issue Request Item",
		child(
			"Production Issue Request Item",
			[
				field("item_code", "Item", "Link", options="Item", reqd=1, in_list_view=1),
				field("recipe_quantity", "Recipe Qty", "Float"),
				field("requested_quantity", "Requested Qty", "Float", reqd=1, in_list_view=1),
				field("issue_quantity", "To Issue", "Float"),
				field("issued_quantity", "Issued Qty", "Float", default="0", read_only=1),
				field("lot_allocations", "Lot Allocations", "Small Text"),
			],
		),
		ctrl("ProductionIssueRequestItem"),
	)

	write_doctype(
		"Production Issue Request",
		doctype(
			"Production Issue Request",
			[
				field("production_serial", "Production Serial", "Data", in_list_view=1),
				field("status", "Status", "Select", options="draft\nopen\nsent_to_store\naccepted\npicking\npicking_done\npartially_issued\nissued\nclosed\ncancelled\ncorrected\ndeleted", default="draft", in_standard_filter=1),
				field("quality_status", "Quality Status", "Select", options="NOT_ASSIGNED\nPENDING\nAPPROVED\nREJECTED_REPICK\nREJECTED_PRODUCTION", default="NOT_ASSIGNED"),
				field("store_issue", "Store Issue", "Link", options="Store Issue", read_only=1),
				field("items", "Items", "Table", options="Production Issue Request Item"),
			],
			autoname="PIR-.YYYY.MM.DD.-.####",
			permissions=perms(extra=[("Production Requester", {"create": 1, "write": 1})]),
		),
		ctrl("ProductionIssueRequest"),
	)

	write_doctype(
		"Labelling Material Request Item",
		child(
			"Labelling Material Request Item",
			[
				field("item_code", "Item", "Link", options="Item", reqd=1, in_list_view=1),
				field("requested_quantity", "Requested Qty", "Float", reqd=1, in_list_view=1),
				field("issued_quantity", "Issued Qty", "Float", default="0", read_only=1),
			],
		),
		ctrl("LabellingMaterialRequestItem"),
	)

	write_doctype(
		"Labelling Material Request",
		doctype(
			"Labelling Material Request",
			[
				field("production_serial", "Production Serial", "Data", reqd=1, in_list_view=1),
				field("status", "Status", "Select", options="draft\nopen\nissued\nclosed\ncancelled", default="draft"),
				field("revision", "Revision", "Int", default="0"),
				field("operation_id", "Operation ID", "Data"),
				field("store_issue", "Store Issue", "Link", options="Store Issue", read_only=1),
				field("items", "Items", "Table", options="Labelling Material Request Item"),
			],
			autoname="LMR-.#####",
			permissions=perms(extra=[("Labelling Requester", {"create": 1, "write": 1})]),
		),
		ctrl("LabellingMaterialRequest"),
	)

	write_doctype(
		"Store Stock Return Item",
		child(
			"Store Stock Return Item",
			[
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("item_code", "Item", "Link", options="Item"),
				field("issued_quantity", "Issued Qty", "Float"),
				field("already_returned_quantity", "Already Returned", "Float", default="0"),
				field("return_quantity", "Return Qty", "Float", reqd=1, in_list_view=1),
				field("issue_line", "Issue Line", "Data"),
				field("source_issue_location", "Source Location", "Link", options="Warehouse"),
				field("location", "Return Location", "Link", options="Warehouse"),
				field("location_code", "Location Code", "Data"),
			],
		),
		ctrl("StoreStockReturnItem"),
	)

	write_doctype(
		"Store Stock Return",
		doctype(
			"Store Stock Return",
			[
				field("link_mode", "Link Mode", "Select", options="against_issue\nstandalone", default="against_issue", reqd=1),
				field("issue", "Store Issue", "Link", options="Store Issue"),
				field("return_type", "Return Type", "Select", options="production_surplus\nproduction_unused\nwrong_issue\ndamaged\nquality_reject\ndispatch_return\nother", default="production_unused", reqd=1),
				field("requested_department", "Requested Department", "Select", options="production\ndispatch\nstore", default="production"),
				field("approval_mode", "Approval Mode", "Select", options="auto\nsupervisor\nmanager", default="auto"),
				field("status", "Status", "Select", options="draft\nsubmitted\napproved\nposted\nrejected\ncancelled", default="draft", in_standard_filter=1),
				field("posting_location", "Post To Location", "Link", options="Warehouse"),
				field("stock_entry", "Stock Entry", "Link", options="Stock Entry", read_only=1),
				field("posted_by", "Posted By", "Link", options="User", read_only=1),
				field("posted_at", "Posted At", "Datetime", read_only=1),
				field("items", "Items", "Table", options="Store Stock Return Item", reqd=1),
			],
			autoname="RET-.YYYY.MM.DD.-.####",
			permissions=perms(extra=[("Production Requester", {"create": 1, "write": 1})]),
		),
		ctrl("StoreStockReturn"),
	)

	write_doctype(
		"Store Vendor Return Item",
		child(
			"Store Vendor Return Item",
			[
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("item_code", "Item", "Link", options="Item"),
				field("location", "Location", "Link", options="Warehouse", reqd=1, in_list_view=1),
				field("on_hand_quantity", "On Hand", "Float", read_only=1),
				field("available_quantity", "Available", "Float", read_only=1),
				field("return_quantity", "Return Qty", "Float", reqd=1, in_list_view=1),
			],
		),
		ctrl("StoreVendorReturnItem"),
	)

	write_doctype(
		"Store Vendor Return",
		doctype(
			"Store Vendor Return",
			[
				field("return_type", "Return Type", "Select", options="damaged\nquality_reject\nother", default="damaged", reqd=1),
				field("status", "Status", "Select", options="draft\nsubmitted\napproved\nposted\nrejected\ncancelled", default="draft"),
				field("supplier", "Supplier", "Link", options="Supplier", reqd=1),
				field("grn", "GRN", "Link", options="Purchase Receipt"),
				field("invoice_number", "Invoice Number", "Data"),
				field("return_reason", "Reason", "Small Text", reqd=1),
				field("photo", "Photo", "Attach Image"),
				field("purchase_receipt", "Return Receipt", "Link", options="Purchase Receipt", read_only=1),
				field("posted_by", "Posted By", "Link", options="User", read_only=1),
				field("posted_at", "Posted At", "Datetime", read_only=1),
				field("items", "Items", "Table", options="Store Vendor Return Item", reqd=1),
			],
			autoname="VRET-.YYYY.MM.DD.-.####",
			permissions=perms(),
		),
		ctrl("StoreVendorReturn"),
	)

	write_doctype(
		"Store Damage Report",
		doctype(
			"Store Damage Report",
			[
				field("issue", "Store Issue", "Link", options="Store Issue", reqd=1),
				field("reported_at", "Reported At", "Datetime", reqd=1),
				field("is_within_window", "Within 2 Hour Window", "Check", read_only=1),
				field("description", "Description", "Small Text", reqd=1),
				field("photo", "Photo", "Attach Image"),
			],
			autoname="DMG-.YYYY.MM.DD.-.####",
			permissions=perms(extra=[("Production Requester", {"create": 1, "write": 1})]),
		),
		ctrl("StoreDamageReport"),
	)

	write_doctype(
		"Store Opening Stock",
		doctype(
			"Store Opening Stock",
			[
				field("item_code", "Item", "Link", options="Item", reqd=1, in_list_view=1),
				field("item_name", "Item Name", "Data", fetch_from="item_code.item_name", read_only=1),
				field("lot_id", "Lot", "Link", options="Batch"),
				field("batch_number", "Supplier Batch", "Data"),
				field("quantity", "Quantity", "Float", reqd=1, in_list_view=1),
				field("location", "Location", "Link", options="Warehouse", reqd=1),
				field("mfg_date", "Manufacture Date", "Date"),
				field("expiry_date", "Expiry Date", "Date"),
				field("unit_cost", "Unit Cost", "Currency", reqd=1),
				field("status", "Status", "Select", options="pending\nposted\nlocked", default="pending"),
				field("stock_entry", "Stock Entry", "Link", options="Stock Entry", read_only=1),
				field("entered_by", "Entered By", "Link", options="User", read_only=1),
				field("posted_at", "Posted At", "Datetime", read_only=1),
			],
			autoname="OPEN-.YYYY.MM.DD.-.####",
			is_submittable=1,
			permissions=perms(submit=True),
		),
		ctrl("StoreOpeningStock"),
	)

	write_doctype(
		"Store Transfer",
		doctype(
			"Store Transfer",
			[
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("item_code", "Item", "Link", options="Item", read_only=1),
				field("from_location", "From", "Link", options="Warehouse", reqd=1),
				field("to_location", "To", "Link", options="Warehouse", reqd=1),
				field("quantity", "Quantity", "Float", reqd=1),
				field("reason", "Reason", "Small Text"),
				field("status", "Status", "Select", options="completed\ncancelled", default="completed", read_only=1),
				field("stock_entry", "Stock Entry", "Link", options="Stock Entry", read_only=1),
				field("transferred_by", "Transferred By", "Link", options="User", read_only=1),
				field("transferred_at", "Transferred At", "Datetime", read_only=1),
			],
			autoname="TRN-.YYYY.MM.DD.-.####",
			is_submittable=1,
			permissions=perms(submit=True),
		),
		ctrl("StoreTransfer"),
	)

	write_doctype(
		"Store Cycle Count Item",
		child(
			"Store Cycle Count Item",
			[
				field("item_code", "Item", "Link", options="Item", reqd=1, in_list_view=1),
				field("lot_id", "Lot", "Link", options="Batch", reqd=1, in_list_view=1),
				field("location", "Location", "Link", options="Warehouse", reqd=1, in_list_view=1),
				field("system_quantity", "System Qty", "Float", read_only=1),
				field("physical_quantity", "Physical Qty", "Float", reqd=1, in_list_view=1),
				field("variance", "Variance", "Float", read_only=1),
			],
		),
		ctrl("StoreCycleCountItem"),
	)

	write_doctype(
		"Store Cycle Count",
		doctype(
			"Store Cycle Count",
			[
				field("status", "Status", "Select", options="pending\ncounted\napproved\nadjusted", default="pending"),
				field("counted_by", "Counted By", "Link", options="User"),
				field("items", "Items", "Table", options="Store Cycle Count Item", reqd=1),
			],
			autoname="CC-.YYYY.MM.DD.-.####",
			permissions=perms(),
		),
		ctrl("StoreCycleCount"),
	)

	write_doctype(
		"Store Adjustment",
		doctype(
			"Store Adjustment",
			[
				field("item_code", "Item", "Link", options="Item", reqd=1),
				field("lot_id", "Lot", "Link", options="Batch", reqd=1),
				field("location", "Location", "Link", options="Warehouse", reqd=1),
				field("adjustment_type", "Type", "Select", options="increase\ndecrease\nset\nexpiry", default="set", reqd=1),
				field("quantity", "Quantity", "Float"),
				field("new_quantity", "New Quantity", "Float"),
				field("new_expiry_date", "New Expiry Date", "Date"),
				field("reason", "Reason", "Small Text", reqd=1),
				field("status", "Status", "Select", options="pending\napproved\nrejected", default="pending"),
				field("cycle_count", "Cycle Count", "Link", options="Store Cycle Count"),
				field("stock_reconciliation", "Stock Reconciliation", "Link", options="Stock Reconciliation", read_only=1),
			],
			autoname="ADJ-.YYYY.MM.DD.-.####",
			is_submittable=1,
			permissions=perms(submit=True),
		),
		ctrl("StoreAdjustment"),
	)

	write_doctype(
		"Store Stock Reconciliation Log",
		doctype(
			"Store Stock Reconciliation Log",
			[
				field("action", "Action", "Select", options="verified\napplied\npending_approval\nrejected\nnote_only\nexcluded\nopening_stock_referral", reqd=1, in_list_view=1),
				field("search_mode", "Search Mode", "Select", options="lot\nlocation\nitem"),
				field("item_code", "Item", "Link", options="Item"),
				field("lot_id", "Lot", "Link", options="Batch"),
				field("location", "Location", "Link", options="Warehouse"),
				field("system_qty", "System Qty", "Float"),
				field("physical_qty", "Physical Qty", "Float"),
				field("reference", "Reference", "Data"),
				field("note", "Note", "Small Text"),
			],
			autoname="SRL-.#####",
			permissions=perms(),
		),
		ctrl("StoreStockReconciliationLog"),
	)

	write_doctype(
		"Store GRN Charge",
		doctype(
			"Store GRN Charge",
			[
				field("grn", "GRN", "Link", options="Purchase Receipt", reqd=1, in_list_view=1),
				field("invoice_number", "Invoice Number", "Data"),
				field("charge_type", "Charge Type", "Select", options="FREIGHT\nUNLOADING", reqd=1, in_list_view=1),
				field("amount", "Amount", "Currency", reqd=1, in_list_view=1),
				field("bilty_number", "Bilty / LR", "Data"),
				field("party_name", "Party", "Data"),
				field("charge_date", "Charge Date", "Date"),
				field("payment_status", "Payment Status", "Select", options="PENDING\nPAID\nNA", default="PENDING"),
				field("source", "Source", "Select", options="GRN_RECEIVE\nPOST_GRN", default="GRN_RECEIVE"),
			],
			autoname="CHG-.#####",
			permissions=perms(),
		),
		ctrl("StoreGRNCharge"),
	)


if __name__ == "__main__":
	build()
	print("doctypes written")
