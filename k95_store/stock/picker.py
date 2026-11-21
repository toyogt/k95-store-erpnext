import frappe
from frappe import _
from frappe.utils import flt, getdate

from k95_store.constants import FROZEN_LOT_STATUSES
from k95_store.stock.lots import get_pending_putaway, is_opening_lot
from k95_store.stock.utils import epsilon, get_receiving_warehouse, is_issuable_warehouse, qty_zero


def get_reserved_qty(batch_no, warehouse, ignore_reservation=None):
	filters = {
		"lot_id": batch_no,
		"location": warehouse,
		"status": "ACTIVE",
	}
	rows = frappe.get_all(
		"Store Stock Reservation",
		filters=filters,
		fields=["name", "quantity"],
	)
	total = 0
	for row in rows:
		if ignore_reservation and row.name == ignore_reservation:
			continue
		total += flt(row.quantity)
	return total


def get_available_balances(item_code=None, batch_no=None, include_receiving=False):
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	receiving = get_receiving_warehouse()
	kwargs = {}
	if item_code:
		kwargs["item_code"] = item_code
	if batch_no:
		kwargs["batch_no"] = batch_no
	rows = get_batch_qty(**kwargs) or []
	if isinstance(rows, (int, float)):
		rows = []

	balances = []
	for row in rows:
		warehouse = row.get("warehouse")
		qty = flt(row.get("qty"))
		lot = row.get("batch_no")
		if qty_zero(qty) or not warehouse or not lot:
			continue
		if not include_receiving and warehouse == receiving:
			continue
		if not is_issuable_warehouse(warehouse):
			continue
		status = frappe.db.get_value("Batch", lot, "custom_lot_status")
		if status in FROZEN_LOT_STATUSES:
			continue
		available = max(0, qty - get_reserved_qty(lot, warehouse))
		if qty_zero(available):
			continue
		batch = frappe.db.get_value(
			"Batch",
			lot,
			["item", "expiry_date", "manufacturing_date", "custom_supplier_batch", "creation"],
			as_dict=True,
		)
		balances.append(
			frappe._dict(
				{
					"item_code": batch.item if batch else item_code,
					"lot_id": lot,
					"warehouse": warehouse,
					"quantity": qty,
					"available_quantity": available,
					"expiry_date": batch.expiry_date if batch else None,
					"manufacturing_date": batch.manufacturing_date if batch else None,
					"supplier_batch": batch.custom_supplier_batch if batch else None,
					"putaway_date": get_putaway_date(lot, warehouse),
					"creation": batch.creation if batch else None,
				}
			)
		)
	return balances


def get_putaway_date(batch_no, warehouse):
	date = frappe.db.sql(
		"""
		select min(posting_date)
		from `tabStock Ledger Entry`
		where batch_no = %s
			and warehouse = %s
			and is_cancelled = 0
			and actual_qty > 0
		""",
		(batch_no, warehouse),
	)
	return date[0][0] if date and date[0][0] else None


def suggest_issue_allocations(item_code, qty, warehouse=None):
	"""FEFO across lots, then FIFO by putaway_date inside a lot."""
	needed = flt(qty)
	if needed <= epsilon():
		return []

	balances = get_available_balances(item_code=item_code)
	if warehouse:
		balances = [row for row in balances if row.warehouse == warehouse]

	balances.sort(
		key=lambda row: (
			getdate(row.expiry_date) if row.expiry_date else getdate("9999-12-31"),
			row.putaway_date or row.creation or getdate("9999-12-31"),
			row.lot_id,
			row.warehouse,
		)
	)

	allocations = []
	for row in balances:
		if needed <= epsilon():
			break
		take = min(row.available_quantity, needed)
		if take <= epsilon():
			continue
		allocations.append(
			frappe._dict(
				{
					"item_code": item_code,
					"lot_id": row.lot_id,
					"warehouse": row.warehouse,
					"quantity": take,
					"expiry_date": row.expiry_date,
					"supplier_batch": row.supplier_batch,
				}
			)
		)
		needed -= take

	if needed > epsilon():
		frappe.throw(
			_("Not enough issuable stock for {0}. Short by {1}.").format(item_code, frappe.utils.fmt_money(needed, format="#.###"))
		)
	return allocations


def pending_putaway_queue():
	receiving = get_receiving_warehouse()
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	rows = []
	for bin_row in frappe.get_all(
		"Bin",
		filters={"warehouse": receiving, "actual_qty": [">", 0]},
		fields=["item_code"],
	):
		batches = get_batch_qty(item_code=bin_row.item_code, warehouse=receiving) or []
		if isinstance(batches, (int, float)):
			continue
		rows.extend(batches)
	queue = []
	for row in rows:
		lot = row.get("batch_no")
		qty = flt(row.get("qty"))
		if not lot or qty_zero(qty):
			continue
		if is_opening_lot(lot):
			continue
		status = frappe.db.get_value("Batch", lot, "custom_lot_status")
		if status in FROZEN_LOT_STATUSES or status == "consumed":
			continue
		batch = frappe.db.get_value(
			"Batch",
			lot,
			["item", "item_name", "custom_supplier_batch", "expiry_date", "custom_grn"],
			as_dict=True,
		)
		if not batch:
			continue
		queue.append(
			{
				"lot_id": lot,
				"item_code": batch.item,
				"item_name": batch.item_name,
				"quantity": qty,
				"pending_putaway_qty": get_pending_putaway(lot),
				"supplier_batch": batch.custom_supplier_batch,
				"expiry_date": batch.expiry_date,
				"grn": batch.custom_grn,
				"warehouse": receiving,
			}
		)
	return queue
