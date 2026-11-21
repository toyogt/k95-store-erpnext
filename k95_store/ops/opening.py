import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from k95_store.stock.lots import create_lot_batch, next_lot_id
from k95_store.stock.utils import epsilon, is_active_location, make_stock_entry


def post_opening(doc):
	if flt(doc.quantity) <= epsilon():
		frappe.throw(_("Opening quantity must be greater than 0."))
	if not is_active_location(doc.location):
		frappe.throw(_("Location {0} is inactive.").format(doc.location))
	if flt(doc.unit_cost) <= 0:
		frappe.throw(_("Unit cost is required for opening stock."))

	lot_id = doc.lot_id or next_lot_id(opening=True)
	doc.lot_id = lot_id
	create_lot_batch(
		doc.item_code,
		lot_id=lot_id,
		opening=True,
		values={
			"manufacturing_date": doc.mfg_date,
			"expiry_date": doc.expiry_date,
			"custom_supplier_batch": doc.batch_number,
			"custom_is_opening_lot": 1,
			"custom_lot_status": "putaway",
			"supplier": None,
		},
	)
	stock_entry = make_stock_entry(
		"Material Receipt",
		[
			{
				"item_code": doc.item_code,
				"qty": doc.quantity,
				"batch_no": lot_id,
				"t_warehouse": doc.location,
				"basic_rate": doc.unit_cost,
			}
		],
		remarks=f"Store Opening Stock {doc.name}",
		extra={"is_opening": "Yes"},
	)
	doc.stock_entry = stock_entry.name
	doc.status = "posted"
	doc.posted_at = now_datetime()
	doc.entered_by = frappe.session.user
	return stock_entry
