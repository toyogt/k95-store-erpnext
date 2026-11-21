import frappe
from frappe.utils import add_days, getdate, nowdate

from k95_store.stock.picker import get_available_balances


def execute(filters=None):
	filters = filters or {}
	days = frappe.utils.cint(filters.get("days") or 30)
	horizon = add_days(nowdate(), days)
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "Lot", "fieldname": "lot_id", "fieldtype": "Link", "options": "Batch", "width": 160},
		{"label": "Supplier Batch", "fieldname": "supplier_batch", "fieldtype": "Data", "width": 120},
		{"label": "Location", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
		{"label": "Available", "fieldname": "available_quantity", "fieldtype": "Float", "width": 100},
		{"label": "Expiry", "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
	]
	rows = []
	for row in get_available_balances(item_code=filters.get("item_code")):
		if not row.expiry_date:
			continue
		if getdate(row.expiry_date) <= getdate(horizon):
			rows.append(row)
	rows.sort(key=lambda r: getdate(r.expiry_date))
	return columns, rows
