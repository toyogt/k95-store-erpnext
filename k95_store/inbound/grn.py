import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate

from k95_store.constants import DEFAULT_EPSILON
from k95_store.inbound.qc import create_damage_report
from k95_store.stock.lots import create_lot_batch, next_lot_id, recompute_lot_status
from k95_store.stock.utils import (
	assert_store_item,
	get_rejected_warehouse,
	get_settings,
	is_store_manager,
)


def before_validate_purchase_receipt(doc, method=None):
	if doc.is_return:
		return
	for row in doc.items or []:
		if row.get("custom_is_reject_line"):
			continue
		basis = row.get("custom_discount_basis") or "Percent"
		if not flt(row.price_list_rate) and flt(row.rate):
			row.price_list_rate = row.rate
		base = flt(row.price_list_rate)
		if not base:
			continue
		if basis == "Amount":
			row.discount_percentage = flt(row.discount_amount) / base * 100
		else:
			row.discount_amount = base * flt(row.discount_percentage) / 100


def validate_purchase_receipt(doc, method=None):
	if doc.is_return:
		return

	_set_line_warehouses(doc)
	_validate_supplier(doc)
	_validate_source_document(doc)
	_validate_bill(doc)
	_validate_items(doc)
	_apply_mismatch(doc)
	_apply_grn_summary(doc)
	_validate_po_qty(doc)
	_filter_supplier_items(doc)
	_set_line_warehouses(doc)


def before_submit_purchase_receipt(doc, method=None):
	if doc.is_return:
		return
	_validate_source_document(doc, strict=True)
	_validate_bill(doc, strict=True)
	_validate_po_qty(doc, strict=True)
	_split_damage_lines(doc)
	_set_line_warehouses(doc)
	for row in doc.items:
		assert_store_item(row.item_code)
		_validate_item_flags(row)
		if not row.custom_lot_id:
			row.custom_lot_id = next_lot_id()
		_ensure_lot_for_row(doc, row)
		row.use_serial_batch_fields = 1
		row.batch_no = row.custom_lot_id


def on_submit_purchase_receipt(doc, method=None):
	if doc.is_return:
		return
	_close_gate(doc)
	_apply_charges(doc)
	_create_inbound_damage_reports(doc)
	for row in doc.items:
		if row.custom_lot_id:
			# reject / pending_qc statuses are set on the batch; do not let recompute wipe them
			if row.get("custom_is_reject_line") or row.get("custom_qc_required"):
				continue
			recompute_lot_status(row.custom_lot_id)


def on_cancel_purchase_receipt(doc, method=None):
	if doc.is_return:
		return
	_reopen_gate(doc)
	for row in doc.items:
		if row.custom_lot_id:
			recompute_lot_status(row.custom_lot_id)


def _arrival_type(doc):
	if doc.get("custom_arrival_type"):
		return doc.custom_arrival_type
	gate = doc.get("custom_gate_entry")
	if not gate:
		return "PO"
	return frappe.db.get_value("Gate Entry", gate, "arrival_type") or "PO"


def _set_line_warehouses(doc):
	settings = get_settings()
	receiving = settings.receiving_warehouse
	rejected = settings.rejected_warehouse
	if receiving and not doc.set_warehouse:
		doc.set_warehouse = receiving
	for row in doc.items:
		if row.get("custom_is_reject_line"):
			if not rejected:
				frappe.throw(_("Set Rejected Warehouse in Store Settings before receiving damaged qty."))
			row.warehouse = rejected
		elif receiving:
			row.warehouse = receiving


def _validate_supplier(doc):
	if not doc.supplier:
		frappe.throw(_("Supplier is required."))
	status = frappe.db.get_value("Supplier", doc.supplier, "custom_approval_status")
	if status in ("HOLD", "BLOCKED"):
		frappe.throw(_("Supplier {0} is {1}.").format(doc.supplier, status))


def _validate_source_document(doc, strict=False):
	arrival = _arrival_type(doc)
	has_po = any(row.purchase_order for row in doc.items if not row.get("custom_is_reject_line"))
	has_typed_po = bool(doc.get("custom_typed_po_number"))
	has_pr = bool(doc.get("custom_linked_pr_number"))
	bypass = bool(doc.get("custom_po_bypass"))

	if arrival == "LOCAL":
		if strict and not has_pr:
			frappe.throw(_("Local arrival requires a linked Material Request / Local Purchase Authorization."))
		if bypass and strict and not is_store_manager():
			frappe.throw(_("Only a Store Manager can use PO Bypass."))
		return

	if arrival == "RETURN":
		return

	if strict and not (has_po or has_typed_po or has_pr or bypass):
		frappe.throw(_("Link a Purchase Order or Material Request, or have a Store Manager tick PO Bypass."))
	if bypass:
		if strict and not is_store_manager():
			frappe.throw(_("PO Bypass is a Store Manager exception, not the local-buy path."))
		if strict and not (doc.get("custom_po_bypass_reason") or "").strip():
			frappe.throw(_("PO Bypass reason is required."))
	if has_typed_po and strict and not has_po:
		frappe.throw(_("Typed PO number is not enough. Pick the open Purchase Order lines."))


def _validate_bill(doc, strict=False):
	_sync_invoice_identity(doc)
	local_without_bill = _arrival_type(doc) == "LOCAL" and not doc.get("custom_supplier_bill_is_final")
	if doc.meta.has_field("custom_supplier_bill_is_final"):
		doc.custom_final_bill_pending = 0 if doc.custom_supplier_bill_is_final else 1
	if not strict:
		return
	if local_without_bill:
		return
	if not _invoice_number(doc):
		frappe.throw(_("Invoice number is required."))
	if not _invoice_date(doc):
		frappe.throw(_("Invoice date is required."))


def _invoice_number(doc):
	return doc.get("custom_invoice_number") or doc.get("bill_no") or doc.get("supplier_delivery_note")


def _invoice_date(doc):
	return doc.get("custom_invoice_date") or doc.get("bill_date")


def _sync_invoice_identity(doc):
	number = (doc.get("custom_invoice_number") or "").strip()
	if number and not doc.get("supplier_delivery_note"):
		doc.supplier_delivery_note = number
	elif doc.get("supplier_delivery_note") and not number:
		doc.custom_invoice_number = doc.supplier_delivery_note
	if number and doc.meta.has_field("bill_no") and not doc.get("bill_no"):
		doc.bill_no = number
	invoice_date = doc.get("custom_invoice_date")
	if invoice_date and doc.meta.has_field("bill_date") and not doc.get("bill_date"):
		doc.bill_date = invoice_date
	elif doc.meta.has_field("bill_date") and doc.get("bill_date") and not invoice_date:
		doc.custom_invoice_date = doc.bill_date


def _validate_items(doc):
	if not doc.items:
		frappe.throw(_("At least one item is required."))
	seen = False
	for row in doc.items:
		if flt(row.qty) > DEFAULT_EPSILON:
			seen = True
		if flt(row.rate) <= 0 and not doc.is_return:
			frappe.throw(_("Unit rate must be greater than 0 and exclusive of GST for {0}.").format(row.item_code))
		assert_store_item(row.item_code)
		if row.item_name:
			master_name = frappe.db.get_value("Item", row.item_code, "item_name")
			if master_name and master_name.strip().lower() != str(row.item_name).strip().lower():
				row.item_name = master_name
		row.custom_qc_required = cint_qc(row.item_code) if not row.get("custom_is_reject_line") else 0
	if not seen:
		frappe.throw(_("At least one line must have receive qty greater than 0."))


def cint_qc(item_code):
	return 1 if frappe.db.get_value("Item", item_code, "custom_qc_required") else 0


def _apply_mismatch(doc):
	for row in doc.items:
		if row.get("custom_is_reject_line"):
			continue
		billed = flt(row.get("custom_ordered_qty"))
		accepted = flt(row.qty)
		rejected = flt(row.get("custom_damaged_qty"))
		row.custom_short_qty = max(billed - accepted - rejected, 0) if billed else 0
		row.custom_excess_qty = max(accepted + rejected - billed, 0) if billed else 0
		_set_po_comparison(row, accepted)
		_set_line_gst(row)
		_set_mismatch_type(row, accepted, rejected)
		row.received_qty = accepted


def _set_po_comparison(row, accepted):
	po_qty = 0
	already = 0
	if row.get("purchase_order_item"):
		values = frappe.db.get_value(
			"Purchase Order Item",
			row.purchase_order_item,
			["qty", "received_qty"],
			as_dict=True,
		)
		if values:
			po_qty = flt(values.qty)
			already = flt(values.received_qty)
	row.custom_po_qty = po_qty
	row.custom_po_received_qty = already
	base = po_qty or flt(row.get("custom_ordered_qty"))
	row.custom_fill_rate = (accepted / base * 100) if base else 0


def _set_line_gst(row):
	net = flt(row.amount) or (flt(row.qty) * flt(row.rate))
	row.custom_gst_amount = net * flt(row.get("custom_gst_rate")) / 100


def _set_mismatch_type(row, accepted, rejected):
	short = flt(row.custom_short_qty)
	if row.custom_po_qty:
		pending = flt(row.custom_po_qty) - flt(row.custom_po_received_qty)
		if accepted - pending > DEFAULT_EPSILON:
			row.custom_mismatch_type = "increased"
			return
	if rejected and short:
		row.custom_mismatch_type = "short_and_damaged"
	elif rejected:
		row.custom_mismatch_type = "damaged"
	elif short:
		row.custom_mismatch_type = "decreased"
	else:
		row.custom_mismatch_type = "none"


def _apply_grn_summary(doc):
	goods = [row for row in doc.items if not row.get("custom_is_reject_line")]
	accepted = sum(flt(row.qty) for row in goods)
	po_qty = sum(flt(row.get("custom_po_qty")) for row in goods)
	billed = sum(flt(row.get("custom_ordered_qty")) for row in goods)
	base = po_qty or billed
	doc.custom_fill_rate = (accepted / base * 100) if base else 0
	gst = sum(flt(row.get("custom_gst_amount")) for row in goods)
	doc.custom_gst_total = gst
	if flt(doc.get("total_taxes_and_charges")):
		grn_value = flt(doc.grand_total)
	else:
		grn_value = flt(doc.grand_total) + gst
	doc.custom_grn_value = grn_value
	invoice_total = flt(doc.get("custom_bill_grand_total"))
	difference = (invoice_total - grn_value) if invoice_total else 0
	doc.custom_value_difference = difference
	doc.custom_value_flag = 1 if invoice_total and abs(difference) > 2 else 0
	_set_delays(doc)


def _set_delays(doc):
	po_date = _po_date(doc)
	doc.custom_po_date = po_date
	posting = getdate(doc.posting_date) if doc.posting_date else None
	doc.custom_po_delay_days = date_diff(posting, po_date) if posting and po_date else 0
	invoice_date = _invoice_date(doc)
	doc.custom_invoice_delay_days = date_diff(posting, invoice_date) if posting and invoice_date else 0


def _po_date(doc):
	po_names = []
	for row in doc.items:
		if row.get("purchase_order") and row.purchase_order not in po_names:
			po_names.append(row.purchase_order)
	if not po_names and doc.get("custom_gate_entry") and frappe.db.has_column("Gate Entry", "purchase_order"):
		gate_po = frappe.db.get_value("Gate Entry", doc.custom_gate_entry, "purchase_order")
		if gate_po:
			po_names.append(gate_po)
	if not po_names and doc.get("custom_typed_po_number"):
		if frappe.db.exists("Purchase Order", doc.custom_typed_po_number):
			po_names.append(doc.custom_typed_po_number)
	if not po_names:
		return None
	return frappe.db.get_value("Purchase Order", po_names[0], "transaction_date")


def _validate_po_qty(doc, strict=False):
	for row in doc.items:
		if row.get("custom_is_reject_line") or not row.get("purchase_order_item"):
			continue
		po_qty, already = frappe.db.get_value(
			"Purchase Order Item",
			row.purchase_order_item,
			["qty", "received_qty"],
		) or (0, 0)
		pending = flt(po_qty) - flt(already)
		if flt(row.qty) - pending > DEFAULT_EPSILON:
			if row.get("custom_mismatch_type") != "increased" and not is_store_manager():
				frappe.throw(
					_("Cannot receive more than pending qty {0} for {1}. Over-receipt needs Store Manager.").format(
						pending, row.item_code
					)
				)
			if strict and not is_store_manager():
				frappe.throw(_("Over-receipt of {0} needs a Store Manager.").format(row.item_code))
		if (row.get("custom_mismatch_type") == "increased") and strict and not is_store_manager():
			frappe.throw(_("Mismatch type Increased is a Store Manager exception."))


def _split_damage_lines(doc):
	additions = []
	for row in doc.items:
		if row.get("custom_is_reject_line"):
			continue
		damaged = flt(row.get("custom_damaged_qty"))
		if damaged <= DEFAULT_EPSILON:
			continue
		additions.append((row, damaged))

	if not additions:
		return
	get_rejected_warehouse()
	for source, damaged in additions:
		already = any(
			r.get("custom_is_reject_line")
			and r.item_code == source.item_code
			and abs(flt(r.qty) - damaged) <= DEFAULT_EPSILON
			for r in doc.items
		)
		if already:
			continue
		doc.append(
			"items",
			{
				"item_code": source.item_code,
				"item_name": source.item_name,
				"qty": damaged,
				"received_qty": damaged,
				"rate": source.rate,
				"uom": source.uom,
				"stock_uom": source.stock_uom,
				"conversion_factor": source.conversion_factor or 1,
				"custom_ordered_qty": 0,
				"custom_damaged_qty": damaged,
				"custom_mismatch_type": "damaged",
				"custom_mismatch_reason": source.get("custom_mismatch_reason") or "Inbound damage",
				"custom_is_reject_line": 1,
				"custom_qc_required": 0,
				"custom_supplier_batch": source.get("custom_supplier_batch"),
				"custom_mfg_date": source.get("custom_mfg_date"),
				"custom_expiry_date": source.get("custom_expiry_date"),
				"description": source.get("description"),
			},
		)


def _filter_supplier_items(doc):
	settings = get_settings()
	if not settings.enable_strict_supplier_item_mapping or not doc.supplier:
		return
	if doc.get("custom_show_all_items"):
		return
	mappings = frappe.get_all(
		"Item Supplier",
		filters={"supplier": doc.supplier, "custom_is_active": 1},
		pluck="parent",
	)
	if not mappings:
		return
	for row in doc.items:
		if row.item_code not in mappings:
			frappe.throw(
				_("Item {0} is not mapped to supplier {1}. Tick Show all items to override.").format(
					row.item_code, doc.supplier
				)
			)


def _validate_item_flags(row):
	item = frappe.get_cached_doc("Item", row.item_code)
	if item.get("custom_mfg_date_required") and not row.get("custom_mfg_date"):
		frappe.throw(_("Manufacture date is required for {0}.").format(row.item_code))
	if item.get("custom_expiry_required") and not row.get("custom_expiry_date"):
		frappe.throw(_("Expiry date is required for {0}.").format(row.item_code))
	min_life = item.get("custom_min_shelf_life_days") or item.get("shelf_life_in_days")
	if min_life and row.get("custom_mfg_date"):
		frappe.msgprint(
			_("Check remaining shelf life for {0} (minimum {1} days).").format(row.item_code, min_life),
			alert=True,
		)


def _lot_status_for_row(row):
	if row.get("custom_is_reject_line"):
		return "rejected"
	if cint_qc(row.item_code):
		return "pending_qc"
	return "pending_putaway"


def _ensure_lot_for_row(doc, row):
	create_lot_batch(
		row.item_code,
		lot_id=row.custom_lot_id,
		values={
			"manufacturing_date": row.get("custom_mfg_date"),
			"expiry_date": row.get("custom_expiry_date"),
			"supplier": doc.supplier,
			"custom_supplier_batch": row.get("custom_supplier_batch"),
			"custom_gate_entry": doc.get("custom_gate_entry"),
			"custom_grn": doc.name,
			"custom_invoice_number": _invoice_number(doc),
			"custom_invoice_date": _invoice_date(doc),
			"custom_lot_status": _lot_status_for_row(row),
			"custom_hold_reason": row.get("custom_mismatch_reason") if row.get("custom_is_reject_line") else None,
			"reference_doctype": "Purchase Receipt",
			"reference_name": doc.name,
		},
	)


def _create_inbound_damage_reports(doc):
	for row in doc.items:
		if not row.get("custom_is_reject_line") or not row.custom_lot_id:
			continue
		create_damage_report(
			source="inbound",
			lot_id=row.custom_lot_id,
			item_code=row.item_code,
			quantity=row.qty,
			grn=doc.name,
			gate_entry=doc.get("custom_gate_entry"),
			description=row.get("custom_mismatch_reason") or "Inbound damaged quantity",
		)


def _close_gate(doc):
	gate = doc.get("custom_gate_entry")
	if not gate:
		return
	frappe.db.set_value("Gate Entry", gate, "status", "CLOSED")


def _reopen_gate(doc):
	gate = doc.get("custom_gate_entry")
	if not gate:
		return
	other = frappe.db.exists(
		"Purchase Receipt",
		{"custom_gate_entry": gate, "docstatus": 1, "name": ["!=", doc.name], "is_return": 0},
	)
	if not other:
		frappe.db.set_value("Gate Entry", gate, "status", "OPEN")


def _apply_charges(doc):
	from k95_store.inbound.charges import create_landed_cost_if_needed

	create_landed_cost_if_needed(doc)
