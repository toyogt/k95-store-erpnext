import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from k95_store.constants import ITEM_CATEGORIES, LOCATION_TYPES, LOT_STATUSES, MODULE, ROLES


def run():
	ensure_roles()
	ensure_custom_fields()
	ensure_property_setters()
	ensure_warehouse_tree()
	ensure_workspace()
	from k95_store.store.workflow import ensure_gate_entry_workflow

	ensure_gate_entry_workflow()
	frappe.clear_cache()


def ensure_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(ignore_permissions=True)


def _field(fieldname, label, fieldtype, **kwargs):
	value = {"fieldname": fieldname, "label": label, "fieldtype": fieldtype}
	value.update(kwargs)
	return value


def ensure_custom_fields():
	category_options = "\n".join(ITEM_CATEGORIES)
	location_options = "\n".join(LOCATION_TYPES)
	lot_status_options = "\n".join(LOT_STATUSES)

	custom_fields = {
		"Item": [
			_field("custom_k95_store_tab", "Store", "Tab Break", insert_after="disabled"),
			_field("custom_store_item", "Store Item", "Check", default="0", insert_after="custom_k95_store_tab"),
			_field(
				"custom_item_category",
				"Store Category",
				"Select",
				options=category_options,
				insert_after="custom_store_item",
			),
			_field("custom_mfg_date_required", "Manufacture Date Required", "Check", default="0"),
			_field("custom_expiry_required", "Expiry Date Required", "Check", default="0"),
			_field("custom_allow_auto_generate", "Allow Auto Batch", "Check", default="0"),
			_field(
				"custom_batch_format_rule",
				"Batch Format Rule",
				"Link",
				options="Batch Format Rule",
			),
			_field(
				"custom_qc_required",
				"QC Required",
				"Check",
				default="0",
				description="GRN creates a pending_qc lot. It cannot be put away to storage until QC is passed.",
			),
			_field("custom_min_shelf_life_days", "Min Shelf Life Days", "Int"),
		],
		"Warehouse": [
			_field("custom_k95_store_section", "Store Location", "Section Break"),
			_field("custom_location_code", "Location Code", "Data", unique=1, in_standard_filter=1),
			_field(
				"custom_location_type",
				"Location Type",
				"Select",
				options=location_options,
				default="storage",
			),
			_field("custom_floor", "Floor", "Data"),
			_field("custom_section", "Section", "Data"),
			_field("custom_place", "Place", "Data"),
			_field("custom_slab", "Slab", "Data"),
			_field("custom_rack", "Rack", "Data"),
			_field("custom_capacity_limit", "Capacity Limit", "Float", description="Stored, not enforced."),
			_field("custom_current_utilization", "Current Utilization", "Float"),
		],
		"Batch": [
			_field("custom_k95_store_section", "Store Lot", "Section Break"),
			_field("custom_supplier_batch", "Supplier Batch", "Data", in_list_view=1, in_standard_filter=1),
			_field(
				"custom_lot_status",
				"Lot Status",
				"Select",
				options=lot_status_options,
				default="pending_putaway",
				in_standard_filter=1,
			),
			_field("custom_is_opening_lot", "Opening Lot", "Check", default="0"),
			_field("custom_gate_entry", "Gate Entry", "Link", options="Gate Entry"),
			_field("custom_grn", "GRN / Purchase Receipt", "Link", options="Purchase Receipt"),
			_field("custom_invoice_number", "Invoice Number", "Data"),
			_field("custom_invoice_date", "Invoice Date", "Date"),
			_field("custom_hold_reason", "Hold Reason", "Small Text"),
		],
		"Purchase Receipt": [
			_field("custom_k95_store_tab", "Store", "Tab Break"),
			_field("custom_gate_entry", "Gate Entry", "Link", options="Gate Entry", in_standard_filter=1),
			_field(
				"custom_arrival_type",
				"Arrival Type",
				"Select",
				options="PO\nInvoice\nLOCAL\nRETURN\nCOURIER",
				fetch_from="custom_gate_entry.arrival_type",
				in_standard_filter=1,
			),
			_field("custom_supplier_bill_is_final", "Supplier Bill Is Final", "Check", default="1"),
			_field("custom_final_bill_pending", "Final Bill Pending", "Check", default="0"),
			_field("custom_po_bypass", "PO Bypass", "Check", default="0"),
			_field(
				"custom_po_bypass_reason",
				"PO Bypass Reason",
				"Small Text",
				depends_on="custom_po_bypass",
				mandatory_depends_on="custom_po_bypass",
			),
			_field("custom_typed_po_number", "Typed PO Number", "Data"),
			_field("custom_linked_pr_number", "Linked Material Request / PR", "Data"),
			_field(
				"custom_bill_grand_total",
				"Invoice Total",
				"Currency",
				description="Total printed on the supplier invoice. A difference of more than ₹2 against the GRN value is flagged.",
			),
			_field(
				"custom_freight_option",
				"Freight Option",
				"Select",
				options="NONE\nEXTRA_NOW\nEXTRA_LATER",
				default="NONE",
			),
			_field(
				"custom_freight_amount",
				"Freight Amount",
				"Currency",
				depends_on="eval:doc.custom_freight_option=='EXTRA_NOW' || doc.custom_freight_option=='EXTRA_LATER'",
			),
			_field(
				"custom_unloading_option",
				"Unloading Option",
				"Select",
				options="NONE\nEXTRA_NOW\nEXTRA_LATER",
				default="NONE",
			),
			_field(
				"custom_unloading_amount",
				"Unloading Amount",
				"Currency",
				depends_on="eval:doc.custom_unloading_option=='EXTRA_NOW' || doc.custom_unloading_option=='EXTRA_LATER'",
			),
			_field(
				"custom_allocation_basis",
				"Charge Allocation Basis",
				"Select",
				options="VALUE\nQTY",
				default="VALUE",
			),
			_field(
				"custom_checklist_run",
				"Checklist Run",
				"Link",
				options="Gate Entry Checklist Run",
				hidden=1,
			),
			_field("custom_show_all_items", "Show All Items", "Check", default="0"),
			_field("custom_invoice_number", "Invoice Number", "Data", in_standard_filter=1, allow_on_submit=1),
			_field("custom_invoice_date", "Invoice Date", "Date", allow_on_submit=1),
			_field("custom_grn_note", "GRN Note", "Small Text", allow_on_submit=1),
			_field("custom_po_date", "PO Date", "Date", read_only=1, allow_on_submit=1),
			_field("custom_po_delay_days", "PO to GRN Delay (days)", "Int", read_only=1, allow_on_submit=1),
			_field(
				"custom_invoice_delay_days",
				"Invoice to GRN Delay (days)",
				"Int",
				read_only=1,
				allow_on_submit=1,
			),
			_field("custom_fill_rate", "Fill Rate %", "Percent", read_only=1, allow_on_submit=1),
			_field(
				"custom_grn_value",
				"GRN Value",
				"Currency",
				read_only=1,
				allow_on_submit=1,
				description="GRN total. Item GST is included when GST is not already in the tax table.",
			),
			_field(
				"custom_value_difference",
				"Invoice vs GRN Difference",
				"Currency",
				read_only=1,
				allow_on_submit=1,
			),
			_field(
				"custom_value_flag",
				"Value Difference Above ₹2",
				"Check",
				read_only=1,
				allow_on_submit=1,
			),
			_field("custom_gst_total", "Item GST Total", "Currency", read_only=1, allow_on_submit=1),
			_field(
				"custom_invoice_images",
				"Invoice Images",
				"Table",
				options="Store Invoice Image",
				allow_on_submit=1,
				description="Invoice photos for this GRN. Copy the gate entry photos or upload more. These are not compressed.",
			),
		],
		"Purchase Receipt Item": [
			_field(
				"custom_mismatch_type",
				"Mismatch Type",
				"Select",
				options="none\ndamaged\ndecreased\nincreased\nshort_and_damaged",
				default="none",
			),
			_field("custom_mismatch_reason", "Mismatch Reason", "Small Text"),
			_field(
				"custom_damaged_qty",
				"Rejected Qty",
				"Float",
				depends_on="",
				in_list_view=1,
				description="Quantity that will be received into the rejected warehouse.",
			),
			_field(
				"custom_ordered_qty",
				"Billed Qty",
				"Float",
				in_list_view=1,
				description="Quantity on the supplier invoice.",
			),
			_field("custom_lot_id", "Lot ID", "Data"),
			_field("custom_is_reject_line", "Reject Line", "Check", default="0"),
			_field("custom_qc_required", "QC Required", "Check", default="0"),
			_field("custom_supplier_batch", "Supplier Batch", "Data"),
			_field("custom_mfg_date", "Manufacture Date", "Date"),
			_field("custom_expiry_date", "Expiry Date", "Date"),
			_field("custom_short_qty", "Short Qty", "Float", read_only=1, in_list_view=1, allow_on_submit=1),
			_field("custom_excess_qty", "Excess Qty", "Float", read_only=1, in_list_view=1, allow_on_submit=1),
			_field("custom_po_qty", "PO Qty", "Float", read_only=1, in_list_view=1, allow_on_submit=1),
			_field(
				"custom_po_received_qty",
				"Already Received Qty",
				"Float",
				read_only=1,
				allow_on_submit=1,
				description="Quantity already received on the purchase order before this GRN.",
			),
			_field("custom_fill_rate", "Fill Rate %", "Percent", read_only=1, in_list_view=1, allow_on_submit=1),
			_field("custom_gst_rate", "GST %", "Percent", in_list_view=1),
			_field("custom_gst_amount", "GST Amount", "Currency", read_only=1, allow_on_submit=1),
			_field(
				"custom_discount_basis",
				"Discount Basis",
				"Select",
				options="Percent\nAmount",
				default="Percent",
				in_list_view=1,
				description="Percent uses Discount %. Amount uses Discount Amount. The line rate is the price after discount.",
			),
		],
		"Supplier": [
			_field(
				"custom_approval_status",
				"Store Approval Status",
				"Select",
				options="APPROVED\nHOLD\nBLOCKED",
				default="APPROVED",
				in_standard_filter=1,
			),
		],
		"Item Supplier": [
			_field("custom_is_preferred", "Preferred", "Check", default="0"),
			_field("custom_is_active", "Active Mapping", "Check", default="1"),
			_field("custom_last_rate", "Last Rate", "Currency"),
		],
		"Quality Inspection": [
			_field(
				"custom_gate_entry",
				"Gate Entry",
				"Link",
				options="Gate Entry",
				insert_after="reference_name",
				in_standard_filter=1,
				allow_on_submit=1,
			),
		],
	}

	create_custom_fields(custom_fields, ignore_validate=True, update=True)


def ensure_property_setters():
	setters = [
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt",
			"field_name": "set_warehouse",
			"property": "description",
			"property_type": "Small Text",
			"value": "Store GRN must land in the Receiving warehouse. Putaway moves stock to racks.",
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt Item",
			"field_name": "discount_percentage",
			"property": "depends_on",
			"property_type": "Data",
			"value": "eval:1",
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt Item",
			"field_name": "discount_amount",
			"property": "depends_on",
			"property_type": "Data",
			"value": "eval:1",
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt Item",
			"field_name": "discount_percentage",
			"property": "in_list_view",
			"property_type": "Check",
			"value": "1",
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt Item",
			"field_name": "discount_amount",
			"property": "in_list_view",
			"property_type": "Check",
			"value": "1",
		},
		{
			"doctype_or_field": "DocField",
			"doc_type": "Purchase Receipt Item",
			"field_name": "discount_percentage",
			"property": "label",
			"property_type": "Data",
			"value": "Discount %",
		},
	]
	for data in setters:
		name = f"{data['doc_type']}-{data['field_name']}-{data['property']}"
		if frappe.db.exists("Property Setter", name):
			frappe.db.set_value("Property Setter", name, "value", data["value"])
			continue
		doc = frappe.get_doc({"doctype": "Property Setter", "name": name, "is_system_generated": 1, **data})
		doc.insert(ignore_permissions=True)


def ensure_warehouse_tree():
	if not frappe.db.exists("DocType", "Store Settings"):
		return
	settings = frappe.get_single("Store Settings")
	company = settings.company or frappe.defaults.get_global_default("company")
	if not company:
		return

	abbr = frappe.db.get_value("Company", company, "abbr")
	if not abbr:
		return

	settings.company = company

	def ensure_wh(name, parent=None, is_group=0, location_type="storage", extra=None):
		wh_name = f"{name} - {abbr}"
		if frappe.db.exists("Warehouse", wh_name):
			return wh_name
		doc = frappe.get_doc(
			{
				"doctype": "Warehouse",
				"warehouse_name": name,
				"company": company,
				"parent_warehouse": parent,
				"is_group": is_group,
				"custom_location_type": location_type,
				"custom_location_code": name.replace(" ", "-").upper() if not is_group else "",
			}
		)
		if extra:
			doc.update(extra)
		if location_type == "rejected":
			doc.is_rejected_warehouse = 1
		doc.insert(ignore_permissions=True)
		return doc.name

	stores = ensure_wh("Stores", is_group=1)
	main = ensure_wh("Main Store", parent=stores, is_group=1)
	receiving = ensure_wh("Receiving", parent=main, location_type="receiving")
	rejected = ensure_wh("Rejected", parent=main, location_type="rejected")
	quarantine = ensure_wh("Quarantine", parent=main, location_type="quarantine")

	updates = {}
	if not settings.stores_group_warehouse:
		updates["stores_group_warehouse"] = main
	if not settings.receiving_warehouse:
		updates["receiving_warehouse"] = receiving
	if not settings.rejected_warehouse:
		updates["rejected_warehouse"] = rejected
	if not settings.quarantine_warehouse:
		updates["quarantine_warehouse"] = quarantine
	if updates:
		frappe.db.set_value("Store Settings", "Store Settings", updates, update_modified=False)


def ensure_workspace():
	if frappe.db.exists("Workspace", "K95 Store") and not frappe.db.exists("Workspace", "Store"):
		frappe.rename_doc("Workspace", "K95 Store", "Store", force=True)
	name = "Store"
	if frappe.db.exists("Workspace", name):
		return
	if not frappe.db.exists("DocType", "Workspace"):
		return

	links = [
		("DocType", "Store Settings", "Store Settings"),
		("DocType", "Gate Entry", "Gate Entry"),
		("DocType", "Purchase Receipt", "Purchase Receipt"),
		("DocType", "Store Putaway", "Store Putaway"),
		("DocType", "Store Issue", "Store Issue"),
		("DocType", "Production Issue Request", "Production Issue Request"),
		("DocType", "Labelling Material Request", "Labelling Material Request"),
		("DocType", "Store Stock Return", "Store Stock Return"),
		("DocType", "Store Vendor Return", "Store Vendor Return"),
		("DocType", "Store Damage Report", "Store Damage Report"),
		("DocType", "Store Opening Stock", "Store Opening Stock"),
		("DocType", "Store Transfer", "Store Transfer"),
		("DocType", "Store Adjustment", "Store Adjustment"),
		("DocType", "Store Cycle Count", "Store Cycle Count"),
		("DocType", "Store Stock Reservation", "Store Stock Reservation"),
		("DocType", "Batch Format Rule", "Batch Format Rule"),
		("Report", "Store Stock Balance", "Store Stock Balance"),
		("Report", "Store Near Expiry", "Store Near Expiry"),
		("DocType", "Item", "Item"),
		("DocType", "Warehouse", "Warehouse"),
		("DocType", "Batch", "Batch"),
	]
	try:
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				"name": name,
				"label": name,
				"title": name,
				"module": MODULE,
				"public": 1,
				"is_hidden": 0,
				"content": '[{"type":"header","data":{"text":"Store"}}]',
				"links": [
					{
						"type": "Link",
						"label": label,
						"link_type": link_type,
						"link_to": link_to,
					}
					for link_type, link_to, label in links
				],
			}
		)
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Store workspace setup")
