import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from k95_store.constants import FROZEN_LOT_STATUSES, HELD_LOT_STATUSES, OPENING_LOT_PREFIXES
from k95_store.stock.utils import epsilon, get_receiving_warehouse, qty_zero


def next_lot_id(opening=False):
	if opening:
		return make_series_name("LOT-OPEN-.#####")
	return make_series_name("LOT-.YYYY.MM.DD.-.####")


def make_series_name(pattern):
	from frappe.model.naming import make_autoname

	return make_autoname(pattern)


def is_opening_lot(batch_no, batch=None):
	if not batch_no:
		return False
	if str(batch_no).startswith(OPENING_LOT_PREFIXES):
		return True
	if batch is None:
		return bool(frappe.db.get_value("Batch", batch_no, "custom_is_opening_lot"))
	return bool(batch.get("custom_is_opening_lot"))


def is_held_lot(batch_no):
	status = frappe.db.get_value("Batch", batch_no, "custom_lot_status")
	return status in HELD_LOT_STATUSES


def get_pending_putaway(batch_no):
	if is_opening_lot(batch_no):
		return 0
	status = frappe.db.get_value("Batch", batch_no, "custom_lot_status")
	if status in FROZEN_LOT_STATUSES:
		return 0
	receiving = get_receiving_warehouse()
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	return flt(get_batch_qty(batch_no, receiving) or 0)


def create_lot_batch(item_code, lot_id=None, values=None, opening=False):
	lot_id = lot_id or next_lot_id(opening=opening)
	if frappe.db.exists("Batch", lot_id):
		return frappe.get_doc("Batch", lot_id)

	item = frappe.get_cached_doc("Item", item_code)
	if not item.has_batch_no:
		frappe.db.set_value("Item", item_code, "has_batch_no", 1)
		item.has_batch_no = 1

	doc = frappe.get_doc(
		{
			"doctype": "Batch",
			"batch_id": lot_id,
			"item": item_code,
			"custom_is_opening_lot": 1 if opening else 0,
			"custom_lot_status": "putaway" if opening else "pending_putaway",
		}
	)
	if values:
		doc.update(values)
	doc.insert(ignore_permissions=True)
	return doc


def validate_batch(doc, method=None):
	if doc.custom_is_opening_lot and not str(doc.batch_id or doc.name).startswith(OPENING_LOT_PREFIXES):
		if not str(doc.batch_id or "").startswith(OPENING_LOT_PREFIXES):
			pass
	if doc.expiry_date and doc.manufacturing_date:
		if getdate(doc.expiry_date) < getdate(doc.manufacturing_date):
			frappe.throw(_("Expiry date cannot be before manufacture date for lot {0}.").format(doc.batch_id))


def recompute_lot_status(batch_no):
	if not batch_no or not frappe.db.exists("Batch", batch_no):
		return
	current = frappe.db.get_value(
		"Batch",
		batch_no,
		["custom_lot_status", "custom_is_opening_lot"],
		as_dict=True,
	)
	if current.custom_lot_status in FROZEN_LOT_STATUSES:
		return

	from erpnext.stock.doctype.batch.batch import get_batch_qty

	qty_map = get_batch_qty(batch_no) or []
	receiving = get_receiving_warehouse()
	pending = 0
	on_hand = 0
	for row in qty_map:
		qty = flt(row.get("qty"))
		warehouse = row.get("warehouse")
		if qty_zero(qty):
			continue
		on_hand += qty
		if warehouse == receiving:
			pending += qty

	if current.custom_is_opening_lot:
		status = "consumed" if qty_zero(on_hand) else ("partial" if issued_qty(batch_no) > epsilon() else "putaway")
	elif pending > epsilon():
		status = "pending_putaway"
	elif qty_zero(on_hand):
		status = "consumed"
	elif issued_qty(batch_no) > epsilon():
		status = "partial"
	else:
		status = "putaway"

	frappe.db.set_value("Batch", batch_no, "custom_lot_status", status, update_modified=False)


def issued_qty(batch_no):
	rows = frappe.db.sql(
		"""
		select coalesce(sum(actual_qty), 0) as qty
		from `tabStock Ledger Entry`
		where batch_no = %s
			and is_cancelled = 0
			and actual_qty < 0
			and voucher_type = 'Stock Entry'
		""",
		batch_no,
	)
	return abs(flt(rows[0][0] if rows else 0))


def on_stock_voucher_submit(doc, method=None):
	_recompute_from_voucher(doc)


def on_stock_voucher_cancel(doc, method=None):
	_recompute_from_voucher(doc)


def _recompute_from_voucher(doc):
	batches = set()
	for row in doc.get("items") or []:
		if row.get("batch_no"):
			batches.add(row.batch_no)
		if row.get("custom_lot_id"):
			batches.add(row.custom_lot_id)
	if getattr(doc, "doctype", None) == "Stock Reconciliation":
		for row in doc.get("items") or []:
			if row.get("batch_no"):
				batches.add(row.batch_no)
	for batch_no in batches:
		recompute_lot_status(batch_no)


def collect_voucher_batches(doc):
	# kept for callers that still import the old name
	_recompute_from_voucher(doc)
