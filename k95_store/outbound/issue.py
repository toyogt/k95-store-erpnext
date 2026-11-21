import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from k95_store.constants import FROZEN_LOT_STATUSES
from k95_store.stock.picker import get_reserved_qty, suggest_issue_allocations
from k95_store.stock.utils import epsilon, is_issuable_warehouse, make_stock_entry, qty_zero


def post_issue(doc):
	if not doc.items:
		frappe.throw(_("Add at least one issue line."))

	entries = []
	for row in doc.items:
		qty = flt(row.issued_quantity)
		if qty <= epsilon():
			frappe.throw(_("Issued quantity must be greater than 0."))
		status = frappe.db.get_value("Batch", row.lot_id, "custom_lot_status")
		if status in FROZEN_LOT_STATUSES:
			frappe.throw(_("Lot {0} is {1} and cannot be issued.").format(row.lot_id, status))
		if not is_issuable_warehouse(row.location):
			frappe.throw(_("Location {0} is not issuable. Stock must be put away first.").format(row.location))
		reserved = get_reserved_qty(row.lot_id, row.location, ignore_reservation=row.get("reservation"))
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		on_hand = flt(get_batch_qty(row.lot_id, row.location) or 0)
		available = on_hand - reserved
		if qty - available > epsilon():
			frappe.throw(
				_("Only {0} available for lot {1} at {2} after reservations.").format(
					available, row.lot_id, row.location
				)
			)
		row.item_code = row.item_code or frappe.db.get_value("Batch", row.lot_id, "item")
		row.location_code = frappe.db.get_value("Warehouse", row.location, "custom_location_code") or row.location
		entries.append(
			{
				"item_code": row.item_code,
				"qty": qty,
				"batch_no": row.lot_id,
				"s_warehouse": row.location,
			}
		)
		if row.get("reservation"):
			frappe.db.set_value("Store Stock Reservation", row.reservation, "status", "CONSUMED")

	stock_entry = make_stock_entry(
		"Material Issue",
		entries,
		remarks=f"Store Issue {doc.name} {doc.issue_type or ''} {doc.reference_number or ''}",
	)
	doc.stock_entry = stock_entry.name
	doc.issued_at = now_datetime()
	doc.issued_by = frappe.session.user
	doc.status = "confirmed"
	return stock_entry


def allocate_for_request(item_code, qty, warehouse=None):
	return suggest_issue_allocations(item_code, qty, warehouse=warehouse)


def create_reservations(reference_doctype, reference_name, allocations, request_line=None):
	docs = []
	for row in allocations:
		doc = frappe.get_doc(
			{
				"doctype": "Store Stock Reservation",
				"reference_doctype": reference_doctype,
				"reference_number": reference_name,
				"request_line_id": request_line,
				"item_code": row.item_code,
				"lot_id": row.lot_id,
				"location": row.warehouse,
				"location_code": frappe.db.get_value("Warehouse", row.warehouse, "custom_location_code"),
				"quantity": row.quantity,
				"status": "ACTIVE",
			}
		)
		doc.insert(ignore_permissions=True)
		docs.append(doc)
	return docs
