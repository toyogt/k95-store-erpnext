import frappe
from frappe import _
from frappe.utils import flt

from k95_store.constants import PUTAWAY_LOCATION_TYPES
from k95_store.stock.lots import get_pending_putaway, is_opening_lot
from k95_store.stock.picker import pending_putaway_queue
from k95_store.stock.utils import (
	epsilon,
	get_location_type,
	get_receiving_warehouse,
	is_active_location,
	make_stock_entry,
)


def get_pending():
	return pending_putaway_queue()


def post_putaway(doc):
	receiving = get_receiving_warehouse()
	totals = {}
	entries = []
	for row in doc.items:
		qty = flt(row.quantity)
		if qty <= epsilon():
			frappe.throw(_("Putaway quantity must be greater than 0."))
		if not is_active_location(row.location):
			frappe.throw(_("Location {0} is inactive.").format(row.location))
		if is_opening_lot(row.lot_id):
			frappe.throw(_("Opening lot {0} is not on the GRN putaway queue.").format(row.lot_id))

		status = frappe.db.get_value("Batch", row.lot_id, "custom_lot_status")
		allowed = PUTAWAY_LOCATION_TYPES.get(status)
		if not allowed:
			frappe.throw(_("Lot {0} is {1} and cannot be put away.").format(row.lot_id, status))
		location_type = get_location_type(row.location)
		if location_type not in allowed:
			frappe.throw(
				_("Lot {0} is {1}. Put away only to {2} locations, not {3}.").format(
					row.lot_id, status, ", ".join(allowed), location_type
				)
			)

		pending = get_pending_putaway(row.lot_id)
		totals[row.lot_id] = totals.get(row.lot_id, 0) + qty
		if totals[row.lot_id] - pending > epsilon():
			frappe.throw(
				_("Putaway qty {0} for lot {1} exceeds pending {2}.").format(
					totals[row.lot_id], row.lot_id, pending
				)
			)
		item_code = frappe.db.get_value("Batch", row.lot_id, "item")
		row.item_code = item_code
		row.location_code = frappe.db.get_value("Warehouse", row.location, "custom_location_code") or row.location
		entries.append(
			{
				"item_code": item_code,
				"qty": qty,
				"batch_no": row.lot_id,
				"s_warehouse": receiving,
				"t_warehouse": row.location,
			}
		)

	if not entries:
		frappe.throw(_("Add at least one putaway line."))

	stock_entry = make_stock_entry(
		"Material Transfer",
		entries,
		remarks=f"Store Putaway {doc.name}",
		extra={"from_warehouse": receiving},
	)
	doc.stock_entry = stock_entry.name
	return stock_entry
