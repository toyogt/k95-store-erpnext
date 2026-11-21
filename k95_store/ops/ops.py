import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from k95_store.constants import PUTAWAY_LOCATION_TYPES
from k95_store.stock.utils import (
	epsilon,
	get_location_type,
	get_receiving_warehouse,
	is_active_location,
	make_stock_entry,
)


def post_transfer(doc):
	if doc.from_location == doc.to_location:
		frappe.throw(_("From and To locations must be different."))
	if doc.from_location == get_receiving_warehouse():
		frappe.throw(_("Do not transfer from Receiving. Use Store Putaway."))
	if not is_active_location(doc.to_location):
		frappe.throw(_("To location {0} is inactive.").format(doc.to_location))
	status = frappe.db.get_value("Batch", doc.lot_id, "custom_lot_status")
	allowed = PUTAWAY_LOCATION_TYPES.get(status)
	if allowed and get_location_type(doc.to_location) not in allowed and status in ("pending_qc", "rejected", "damaged"):
		frappe.throw(_("Lot {0} is {1} and cannot move to {2}.").format(doc.lot_id, status, doc.to_location))
	if flt(doc.quantity) <= epsilon():
		frappe.throw(_("Transfer quantity must be at least 0.01."))
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	on_hand = flt(get_batch_qty(doc.lot_id, doc.from_location) or 0)
	if flt(doc.quantity) - on_hand > epsilon():
		frappe.throw(_("Only {0} on hand at {1}.").format(on_hand, doc.from_location))

	item_code = doc.item_code or frappe.db.get_value("Batch", doc.lot_id, "item")
	stock_entry = make_stock_entry(
		"Material Transfer",
		[
			{
				"item_code": item_code,
				"qty": doc.quantity,
				"batch_no": doc.lot_id,
				"s_warehouse": doc.from_location,
				"t_warehouse": doc.to_location,
			}
		],
		remarks=f"Store Transfer {doc.name}",
	)
	doc.stock_entry = stock_entry.name
	doc.status = "completed"
	doc.transferred_by = frappe.session.user
	doc.transferred_at = now_datetime()
	return stock_entry


def post_adjustment(doc):
	if not (doc.reason or "").strip():
		frappe.throw(_("Reason is required."))
	item_code = doc.item_code or frappe.db.get_value("Batch", doc.lot_id, "item")
	if doc.adjustment_type == "expiry":
		if not doc.new_expiry_date:
			frappe.throw(_("New expiry date is required."))
		frappe.db.set_value("Batch", doc.lot_id, "expiry_date", doc.new_expiry_date)
		doc.status = "approved"
		return

	from erpnext.stock.doctype.batch.batch import get_batch_qty

	current = flt(get_batch_qty(doc.lot_id, doc.location) or 0)
	target = flt(doc.new_quantity)
	if doc.adjustment_type == "increase":
		target = current + flt(doc.quantity)
	elif doc.adjustment_type == "decrease":
		target = current - flt(doc.quantity)
	if target < 0:
		frappe.throw(_("Adjustment would make quantity negative."))

	recon = frappe.new_doc("Stock Reconciliation")
	recon.purpose = "Stock Reconciliation"
	recon.company = frappe.get_single("Store Settings").company or frappe.defaults.get_global_default("company")
	recon.append(
		"items",
		{
			"item_code": item_code,
			"warehouse": doc.location,
			"qty": target,
			"use_serial_batch_fields": 1,
			"batch_no": doc.lot_id,
		},
	)
	recon.insert(ignore_permissions=True)
	recon.submit()
	doc.stock_reconciliation = recon.name
	doc.status = "approved"
	write_recon_log(
		action="applied",
		item_code=item_code,
		lot_id=doc.lot_id,
		location=doc.location,
		system_qty=current,
		physical_qty=target,
		reference=doc.name,
		note=doc.reason,
	)
	return recon


def write_recon_log(**kwargs):
	doc = frappe.get_doc({"doctype": "Store Stock Reconciliation Log", **kwargs})
	doc.insert(ignore_permissions=True)
	return doc


def apply_cycle_count(doc):
	if doc.status != "approved":
		frappe.throw(_("Cycle count must be approved before adjustment."))
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	for row in doc.items:
		system_qty = flt(get_batch_qty(row.lot_id, row.location) or 0)
		row.system_quantity = system_qty
		row.variance = flt(row.physical_quantity) - system_qty
		if abs(row.variance) <= epsilon():
			write_recon_log(
				action="verified",
				item_code=row.item_code,
				lot_id=row.lot_id,
				location=row.location,
				system_qty=system_qty,
				physical_qty=row.physical_quantity,
				reference=doc.name,
			)
			continue
		if system_qty <= epsilon() and flt(row.physical_quantity) > epsilon():
			write_recon_log(
				action="opening_stock_referral",
				item_code=row.item_code,
				lot_id=row.lot_id,
				location=row.location,
				system_qty=system_qty,
				physical_qty=row.physical_quantity,
				reference=doc.name,
				note="Zero system qty cannot be applied as a reconcile. Use Store Opening Stock.",
			)
			frappe.throw(
				_("Row for {0} has zero system qty. Use Store Opening Stock, not cycle count apply.").format(
					row.item_code
				)
			)
		adj = frappe.get_doc(
			{
				"doctype": "Store Adjustment",
				"item_code": row.item_code,
				"lot_id": row.lot_id,
				"location": row.location,
				"adjustment_type": "set",
				"new_quantity": row.physical_quantity,
				"reason": f"Cycle count {doc.name}",
				"cycle_count": doc.name,
			}
		)
		adj.insert(ignore_permissions=True)
		adj.submit()
		post_adjustment(adj)
		adj.db_set("status", "approved")
	doc.status = "adjusted"
