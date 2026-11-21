import frappe
from frappe import _
from frappe.utils import flt

from k95_store.constants import DEFAULT_EPSILON, FROZEN_LOT_STATUSES, HELD_LOT_STATUSES, RETURNABLE_LOCATION_TYPES


def get_settings():
	return frappe.get_single("Store Settings")


def epsilon():
	return flt(get_settings().float_epsilon) or DEFAULT_EPSILON


def qty_zero(qty):
	return abs(flt(qty)) <= epsilon()


def get_receiving_warehouse():
	warehouse = get_settings().receiving_warehouse
	if not warehouse:
		frappe.throw(_("Set Receiving Warehouse in Store Settings."))
	return warehouse


def get_rejected_warehouse():
	warehouse = get_settings().rejected_warehouse
	if not warehouse:
		frappe.throw(_("Set Rejected Warehouse in Store Settings."))
	return warehouse


def get_quarantine_warehouse():
	return get_settings().quarantine_warehouse


def is_store_manager():
	return bool(set(frappe.get_roles()) & {"Store Manager", "System Manager"})


def is_returnable_warehouse(warehouse):
	if not warehouse or frappe.db.get_value("Warehouse", warehouse, "disabled"):
		return False
	return get_location_type(warehouse) in RETURNABLE_LOCATION_TYPES


def get_company():
	company = get_settings().company or frappe.defaults.get_global_default("company")
	if not company:
		frappe.throw(_("Set Company in Store Settings."))
	return company


def get_location_type(warehouse):
	return frappe.db.get_value("Warehouse", warehouse, "custom_location_type") or "storage"


def is_issuable_warehouse(warehouse):
	if not warehouse:
		return False
	if frappe.db.get_value("Warehouse", warehouse, "disabled"):
		return False
	return get_location_type(warehouse) == "storage"


def is_active_location(warehouse):
	return bool(warehouse) and not cint_disabled(warehouse)


def cint_disabled(warehouse):
	return frappe.utils.cint(frappe.db.get_value("Warehouse", warehouse, "disabled"))


def assert_store_item(item_code):
	if not item_code:
		frappe.throw(_("Item is required."))
	if not frappe.db.exists("Item", item_code):
		frappe.throw(_("Item {0} is not in Item Master.").format(item_code), title="ORPHAN_ITEM_CODE")
	disabled = frappe.db.get_value("Item", item_code, "disabled")
	if disabled:
		frappe.throw(_("Item {0} is disabled.").format(item_code))


def get_batch_qty_in_warehouse(batch_no, warehouse):
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return flt(get_batch_qty(batch_no, warehouse, item_code=None) or 0)


def get_item_for_batch(batch_no):
	return frappe.db.get_value("Batch", batch_no, "item")


def make_stock_entry(purpose, items, company=None, remarks=None, extra=None):
	doc = frappe.new_doc("Stock Entry")
	doc.purpose = purpose
	doc.company = company or get_company()
	doc.stock_entry_type = purpose
	if remarks:
		doc.remarks = remarks
	if extra:
		doc.update(extra)
	for row in items:
		row = frappe._dict(row)
		child = {
			"item_code": row.item_code,
			"qty": row.qty,
			"uom": row.uom or frappe.db.get_value("Item", row.item_code, "stock_uom"),
			"stock_uom": frappe.db.get_value("Item", row.item_code, "stock_uom"),
			"conversion_factor": row.conversion_factor or 1,
			"use_serial_batch_fields": 1,
			"batch_no": row.batch_no,
			"s_warehouse": row.get("s_warehouse"),
			"t_warehouse": row.get("t_warehouse"),
		}
		if row.get("basic_rate"):
			child["basic_rate"] = row.basic_rate
		doc.append("items", child)
	doc.insert(ignore_permissions=True)
	doc.submit()
	return doc


def validate_stock_entry(doc, method=None):
	settings = get_settings()
	receiving = settings.receiving_warehouse
	if not receiving:
		return

	if doc.purpose == "Material Issue":
		for row in doc.items:
			if row.s_warehouse == receiving:
				frappe.throw(_("Cannot issue from Receiving. Put the lot away first."))
			if row.s_warehouse and not is_issuable_warehouse(row.s_warehouse):
				if get_location_type(row.s_warehouse) in ("rejected", "quarantine", "receiving"):
					frappe.throw(
						_("Warehouse {0} is not issuable ({1}).").format(
							row.s_warehouse, get_location_type(row.s_warehouse)
						)
					)
			if row.batch_no:
				status = frappe.db.get_value("Batch", row.batch_no, "custom_lot_status")
				if status in FROZEN_LOT_STATUSES:
					frappe.throw(_("Lot {0} is {1} and cannot be issued.").format(row.batch_no, status))

	if doc.purpose == "Material Transfer":
		for row in doc.items:
			if not row.s_warehouse or row.s_warehouse != receiving:
				continue
			status = frappe.db.get_value("Batch", row.batch_no, "custom_lot_status") if row.batch_no else None
			target_type = get_location_type(row.t_warehouse)
			if status == "pending_putaway" and target_type == "storage":
				continue
			if status in ("pending_qc", "pending_putaway") and target_type in ("rejected", "quarantine"):
				continue
			if status in HELD_LOT_STATUSES and target_type == "rejected":
				continue
			frappe.throw(
				_("Receiving stock can only move through Store Putaway to a storage rack, or QC fail to Rejected.")
			)
