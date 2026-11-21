import frappe

from k95_store.stock.picker import get_available_balances, pending_putaway_queue


def execute(filters=None):
	filters = filters or {}
	columns = [
		{"label": "Item", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": "Lot", "fieldname": "lot_id", "fieldtype": "Link", "options": "Batch", "width": 160},
		{"label": "Supplier Batch", "fieldname": "supplier_batch", "fieldtype": "Data", "width": 120},
		{"label": "Location", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
		{"label": "On Hand", "fieldname": "quantity", "fieldtype": "Float", "width": 100},
		{"label": "Available", "fieldname": "available_quantity", "fieldtype": "Float", "width": 100},
		{"label": "Expiry", "fieldname": "expiry_date", "fieldtype": "Date", "width": 110},
		{"label": "Putaway Date", "fieldname": "putaway_date", "fieldtype": "Date", "width": 110},
	]
	rows = get_available_balances(item_code=filters.get("item_code"), batch_no=filters.get("lot_id"))
	if filters.get("include_receiving"):
		for row in pending_putaway_queue():
			rows.append(
				{
					"item_code": row["item_code"],
					"lot_id": row["lot_id"],
					"supplier_batch": row.get("supplier_batch"),
					"warehouse": row["warehouse"],
					"quantity": row["quantity"],
					"available_quantity": 0,
					"expiry_date": row.get("expiry_date"),
					"putaway_date": None,
				}
			)
	return columns, rows
