import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from k95_store.constants import DEFAULT_AUTO_APPROVE_PERCENT, DEFAULT_AUTO_APPROVE_QTY
from k95_store.stock.utils import epsilon, get_settings, is_issuable_warehouse, is_returnable_warehouse, make_stock_entry


def should_auto_approve(doc):
	if doc.doctype == "Store Vendor Return":
		return False
	if doc.return_type in ("damaged", "quality_reject"):
		return False
	settings = get_settings()
	percent_limit = flt(settings.auto_approve_return_percent) or DEFAULT_AUTO_APPROVE_PERCENT
	qty_limit = flt(settings.auto_approve_return_qty) or DEFAULT_AUTO_APPROVE_QTY
	for row in doc.items:
		issued = flt(row.issued_quantity)
		returning = flt(row.return_quantity)
		if returning > qty_limit + epsilon():
			return False
		if issued and (returning / issued) * 100 > percent_limit + epsilon():
			return False
	return True


def validate_stock_return(doc):
	if not doc.items:
		frappe.throw(_("Add at least one return line."))
	for row in doc.items:
		qty = flt(row.return_quantity)
		if qty <= epsilon():
			frappe.throw(_("Return quantity must be at least 0.01."))
		if doc.link_mode == "against_issue":
			already = flt(row.already_returned_quantity)
			issued = flt(row.issued_quantity)
			if qty + already - issued > epsilon():
				frappe.throw(
					_("Return qty for lot {0} exceeds issued minus already returned.").format(row.lot_id)
				)
		elif doc.link_mode == "standalone":
			from erpnext.stock.doctype.batch.batch import get_batch_qty

			on_hand = 0
			qty_map = get_batch_qty(row.lot_id) or []
			if isinstance(qty_map, (int, float)):
				on_hand = flt(qty_map)
			else:
				on_hand = sum(flt(r.get("qty")) for r in qty_map)
			if on_hand > epsilon():
				frappe.throw(_("Standalone return is blocked while lot {0} still has on-hand qty.").format(row.lot_id))


def post_stock_return(doc):
	if doc.status != "approved":
		frappe.throw(_("Return must be approved before posting."))
	if not doc.posting_location:
		frappe.throw(_("Choose a return location at post."))
	if not is_issuable_warehouse(doc.posting_location):
		frappe.throw(_("Return location must be an active storage rack."))

	entries = []
	for row in doc.items:
		row.item_code = row.item_code or frappe.db.get_value("Batch", row.lot_id, "item")
		row.location = doc.posting_location
		row.location_code = frappe.db.get_value("Warehouse", doc.posting_location, "custom_location_code")
		entries.append(
			{
				"item_code": row.item_code,
				"qty": row.return_quantity,
				"batch_no": row.lot_id,
				"t_warehouse": doc.posting_location,
			}
		)
		if doc.issue and row.issue_line:
			current = flt(frappe.db.get_value("Store Issue Item", row.issue_line, "returned_quantity"))
			frappe.db.set_value("Store Issue Item", row.issue_line, "returned_quantity", current + flt(row.return_quantity))

	stock_entry = make_stock_entry(
		"Material Receipt",
		entries,
		remarks=f"Store Stock Return {doc.name}",
	)
	doc.stock_entry = stock_entry.name
	doc.status = "posted"
	doc.posted_by = frappe.session.user
	doc.posted_at = now_datetime()
	_update_issue_return_status(doc)
	return stock_entry


def _update_issue_return_status(doc):
	if not doc.issue:
		return
	issue = frappe.get_doc("Store Issue", doc.issue)
	full = True
	any_return = False
	for row in issue.items:
		if flt(row.returned_quantity) > epsilon():
			any_return = True
		if flt(row.returned_quantity) + epsilon() < flt(row.issued_quantity):
			full = False
	issue.return_status = "full" if full and any_return else ("partial" if any_return else "none")
	issue.db_set("return_status", issue.return_status)


def validate_vendor_return(doc):
	if not doc.items:
		frappe.throw(_("Add at least one vendor return line."))
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	for row in doc.items:
		qty = flt(row.return_quantity)
		if qty <= epsilon():
			frappe.throw(_("Return quantity must be at least 0.01."))
		if not is_returnable_warehouse(row.location):
			frappe.throw(
				_("Vendor return needs a storage or rejected balance. Put damaged lots to Rejected first.")
			)
		on_hand = flt(get_batch_qty(row.lot_id, row.location) or 0)
		row.on_hand_quantity = on_hand
		row.available_quantity = on_hand
		if qty - on_hand > epsilon():
			frappe.throw(_("Only {0} on hand for lot {1} at {2}.").format(on_hand, row.lot_id, row.location))


def post_vendor_return(doc):
	if doc.status != "approved":
		frappe.throw(_("Vendor return must be approved by a manager before posting."))
	pr = frappe.new_doc("Purchase Receipt")
	pr.is_return = 1
	pr.company = frappe.get_single("Store Settings").company or frappe.defaults.get_global_default("company")
	pr.supplier = doc.supplier
	pr.return_against = doc.grn
	pr.custom_gate_entry = frappe.db.get_value("Purchase Receipt", doc.grn, "custom_gate_entry") if doc.grn else None
	for row in doc.items:
		item_code = row.item_code or frappe.db.get_value("Batch", row.lot_id, "item")
		pr.append(
			"items",
			{
				"item_code": item_code,
				"qty": -abs(flt(row.return_quantity)),
				"warehouse": row.location,
				"use_serial_batch_fields": 1,
				"batch_no": row.lot_id,
				"purchase_order": None,
			},
		)
	pr.insert(ignore_permissions=True)
	pr.submit()
	doc.purchase_receipt = pr.name
	doc.status = "posted"
	doc.posted_by = frappe.session.user
	doc.posted_at = now_datetime()
	return pr
