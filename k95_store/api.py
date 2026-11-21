import frappe
from frappe import _

from k95_store.inbound.putaway import get_pending
from k95_store.inbound.qc import fail_lot, pass_lot
from k95_store.stock.picker import get_available_balances, suggest_issue_allocations


@frappe.whitelist()
def pending_putaway():
	return get_pending()


@frappe.whitelist()
def available_balances(item_code=None, batch_no=None):
	return get_available_balances(item_code=item_code, batch_no=batch_no)


@frappe.whitelist()
def suggest_issue(item_code, qty, warehouse=None):
	return suggest_issue_allocations(item_code, qty, warehouse=warehouse)


@frappe.whitelist()
def supplier_items(supplier, show_all=0):
	show_all = frappe.utils.cint(show_all)
	if not supplier:
		return []
	mapped = frappe.get_all(
		"Item Supplier",
		filters={"supplier": supplier},
		fields=["parent as item_code", "custom_is_active", "custom_is_preferred", "custom_last_rate"],
	)
	active = [row for row in mapped if row.custom_is_active != 0]
	if active and not show_all:
		item_codes = [row.item_code for row in active]
		return frappe.get_all(
			"Item",
			filters={"name": ["in", item_codes], "disabled": 0},
			fields=["name", "item_name", "stock_uom", "has_batch_no", "custom_qc_required"],
		)
	if mapped and not show_all:
		frappe.msgprint(_("This supplier has no active item mappings. Showing the full catalogue."), alert=True)
	return frappe.get_all(
		"Item",
		filters={"disabled": 0, "is_stock_item": 1},
		fields=["name", "item_name", "stock_uom", "has_batch_no", "custom_qc_required"],
		limit_page_length=500,
	)


def _photo_urls(value):
	if not value:
		return []
	if isinstance(value, (list, tuple)):
		items = value
	else:
		text = str(value).strip()
		if text.startswith("["):
			items = frappe.parse_json(text) or []
		else:
			items = [text]
	urls = []
	for item in items:
		url = item.get("image") or item.get("file_url") if isinstance(item, dict) else item
		if url:
			urls.append(url)
	return urls


@frappe.whitelist()
def create_gate_entry(
	transport_type,
	arrival_type="PO",
	driver_number=None,
	vehicle_number=None,
	driver_name=None,
	supplier_name=None,
	notes=None,
	vehicle_photo=None,
	invoice_photo=None,
	material_photo=None,
):
	from frappe.utils import now_datetime

	doc = frappe.get_doc(
		{
			"doctype": "Gate Entry",
			"arrived_at": now_datetime(),
			"transport_type": transport_type,
			"arrival_type": arrival_type or "PO",
			"driver_number": driver_number,
			"vehicle_number": vehicle_number,
			"driver_name": driver_name,
			"supplier_name": supplier_name,
			"notes": notes,
			"status": "OPEN",
			"workflow_state": "Draft",
		}
	)
	for fieldname, value in (
		("vehicle_photo", vehicle_photo),
		("invoice_photo", invoice_photo),
		("material_photo", material_photo),
	):
		for file_url in _photo_urls(value):
			doc.append(fieldname, {"image": file_url})
	doc.insert()
	return {
		"name": doc.name,
		"status": doc.status,
		"arrival_type": doc.arrival_type,
		"workflow_state": doc.workflow_state,
	}


@frappe.whitelist()
def hold_lot(batch_no, status, reason=None):
	frappe.only_for(("Store Manager", "System Manager", "Store User"))
	if status not in ("rejected", "damaged", "pending_putaway"):
		frappe.throw(_("Status must be rejected, damaged, or pending_putaway."))
	if status in ("rejected", "damaged"):
		if not (reason or "").strip():
			frappe.throw(_("Reason is required."))
		current = frappe.db.get_value("Batch", batch_no, "custom_lot_status")
		if current == "pending_qc" or current == "pending_putaway":
			return fail_lot(batch_no, reason=reason)
	frappe.db.set_value(
		"Batch",
		batch_no,
		{"custom_lot_status": status, "custom_hold_reason": reason},
	)
	return {"lot_id": batch_no, "status": status}


@frappe.whitelist()
def pass_qc(batch_no, notes=None):
	return pass_lot(batch_no, notes=notes)


@frappe.whitelist()
def fail_qc(batch_no, reason=None):
	return fail_lot(batch_no, reason=reason)
