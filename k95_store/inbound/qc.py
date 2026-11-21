import frappe
from frappe import _
from frappe.utils import flt, now_datetime

from k95_store.constants import QC_PENDING_STATUSES
from k95_store.stock.utils import get_receiving_warehouse, get_rejected_warehouse, make_stock_entry, qty_zero


def pass_lot(batch_no, notes=None):
	batch = frappe.get_doc("Batch", batch_no)
	if batch.custom_lot_status not in QC_PENDING_STATUSES:
		frappe.throw(_("Lot {0} is {1}, not pending QC.").format(batch_no, batch.custom_lot_status))
	batch.db_set(
		{
			"custom_lot_status": "pending_putaway",
			"custom_hold_reason": notes or "",
		}
	)
	return {"lot_id": batch_no, "status": "pending_putaway"}


def fail_lot(batch_no, reason=None):
	if not (reason or "").strip():
		frappe.throw(_("QC fail reason is required."))
	batch = frappe.get_doc("Batch", batch_no)
	if batch.custom_lot_status not in QC_PENDING_STATUSES and batch.custom_lot_status != "pending_putaway":
		frappe.throw(_("Lot {0} cannot be failed from status {1}.").format(batch_no, batch.custom_lot_status))

	receiving = get_receiving_warehouse()
	rejected = get_rejected_warehouse()
	from erpnext.stock.doctype.batch.batch import get_batch_qty

	qty = flt(get_batch_qty(batch_no, receiving) or 0)
	stock_entry = None
	if not qty_zero(qty):
		stock_entry = make_stock_entry(
			"Material Transfer",
			[
				{
					"item_code": batch.item,
					"qty": qty,
					"batch_no": batch_no,
					"s_warehouse": receiving,
					"t_warehouse": rejected,
				}
			],
			remarks=f"QC fail {batch_no}: {reason}",
		)

	batch.db_set({"custom_lot_status": "rejected", "custom_hold_reason": reason})
	report = create_damage_report(
		source="qc_fail",
		lot_id=batch_no,
		item_code=batch.item,
		quantity=qty,
		grn=batch.custom_grn,
		gate_entry=batch.get("custom_gate_entry"),
		description=reason,
	)
	return {
		"lot_id": batch_no,
		"status": "rejected",
		"stock_entry": stock_entry.name if stock_entry else None,
		"damage_report": report.name if report else None,
	}


def link_quality_inspection(doc, method=None):
	if not doc.meta.has_field("custom_gate_entry") or doc.get("custom_gate_entry"):
		return
	gate = None
	if doc.reference_type == "Purchase Receipt" and doc.reference_name:
		gate = frappe.db.get_value("Purchase Receipt", doc.reference_name, "custom_gate_entry")
	if not gate and doc.get("batch_no"):
		gate = frappe.db.get_value("Batch", doc.batch_no, "custom_gate_entry")
	if gate:
		doc.custom_gate_entry = gate


def create_damage_report(
	source, lot_id, item_code, quantity, description, grn=None, issue=None, photo=None, gate_entry=None
):
	if not gate_entry and lot_id:
		gate_entry = frappe.db.get_value("Batch", lot_id, "custom_gate_entry")
	if not gate_entry and grn:
		gate_entry = frappe.db.get_value("Purchase Receipt", grn, "custom_gate_entry")
	doc = frappe.get_doc(
		{
			"doctype": "Store Damage Report",
			"source": source,
			"lot_id": lot_id,
			"item_code": item_code,
			"quantity": quantity,
			"grn": grn,
			"gate_entry": gate_entry,
			"issue": issue,
			"description": description,
			"photo": photo,
			"reported_at": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc
