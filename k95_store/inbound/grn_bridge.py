import frappe
from frappe import _
from frappe.utils import flt


def get_purchase_receipt_dashboard(data=None):
	data = frappe._dict(data or {})
	fieldnames = data.setdefault("non_standard_fieldnames", {})
	fieldnames["Store Debit Note"] = "grn"
	fieldnames["Store Putaway"] = "grn"
	internal = data.setdefault("internal_links", {})
	internal["Gate Entry"] = "custom_gate_entry"
	transactions = data.setdefault("transactions", [])
	for row in transactions:
		if row.get("label") in ("Reference", _("Reference")):
			if "Gate Entry" not in row["items"]:
				row["items"].append("Gate Entry")
			break
	else:
		transactions.append({"label": _("Reference"), "items": ["Gate Entry"]})
	transactions.append({"label": _("Store"), "items": ["Store Debit Note", "Store Putaway"]})
	return data


@frappe.whitelist()
def open_gate_entries_without_grn():
	frappe.has_permission("Gate Entry", "read", throw=True)
	rows = frappe.db.sql(
		"""
		select ge.name
		from `tabGate Entry` ge
		where ge.status = 'OPEN'
			and ge.docstatus < 2
			and not exists (
				select 1
				from `tabPurchase Receipt` pr
				where pr.custom_gate_entry = ge.name
					and pr.docstatus < 2
					and ifnull(pr.is_return, 0) = 0
			)
		order by ge.arrived_at desc
		"""
	)
	return [row[0] for row in rows]


@frappe.whitelist()
def make_purchase_receipt_from_gate_entry(gate_entry):
	frappe.has_permission("Gate Entry", "read", doc=gate_entry, throw=True)
	frappe.has_permission("Purchase Receipt", "create", throw=True)
	gate = frappe.get_doc("Gate Entry", gate_entry)
	existing = _existing_receipt(gate.name)
	if existing:
		return {"name": existing, "created": 0}
	if not gate.supplier:
		frappe.throw(_("Select a Supplier on the gate entry before creating the GRN."))
	pr = _new_receipt(gate)
	_copy_invoice_images(pr, gate)
	for row in pr.items:
		if not row.custom_ordered_qty:
			row.custom_ordered_qty = row.qty
	pr.insert()
	return {"name": pr.name, "created": 1}


@frappe.whitelist()
def gate_entry_for_receipt(gate_entry):
	frappe.has_permission("Gate Entry", "read", doc=gate_entry, throw=True)
	if not (
		frappe.has_permission("Purchase Receipt", "create")
		or frappe.has_permission("Purchase Receipt", "write")
	):
		frappe.throw(_("Not permitted to update a GRN."), frappe.PermissionError)
	gate = frappe.get_doc("Gate Entry", gate_entry)
	items = _po_items(gate.purchase_order) if gate.purchase_order else []
	return {
		"gate_entry": gate.name,
		"supplier": gate.supplier,
		"supplier_name": gate.supplier_name,
		"arrival_type": gate.arrival_type,
		"po_number": gate.po_number or gate.purchase_order,
		"purchase_order": gate.purchase_order,
		"notes": gate.notes,
		"items": items,
		"images": [row.image for row in (gate.invoice_photo or []) if row.image],
	}


@frappe.whitelist()
def make_debit_note(purchase_receipt):
	frappe.has_permission("Purchase Receipt", "read", doc=purchase_receipt, throw=True)
	pr = frappe.get_doc("Purchase Receipt", purchase_receipt)
	existing = frappe.db.get_value("Store Debit Note", {"grn": pr.name, "status": "Draft"}, "name")
	if existing:
		return {"name": existing, "created": 0}
	lines = []
	for row in pr.items:
		if row.get("custom_is_reject_line"):
			continue
		short = flt(row.get("custom_short_qty"))
		rejected = flt(row.get("custom_damaged_qty"))
		if short <= 0 and rejected <= 0:
			continue
		rate = flt(row.rate)
		lines.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"short_qty": short,
				"rejected_qty": rejected,
				"rate": rate,
				"amount": (short + rejected) * rate,
			}
		)
	if not lines:
		frappe.throw(
			_("There is no short or rejected quantity on this GRN."),
			title=_("Nothing to claim"),
		)
	note = frappe.get_doc(
		{
			"doctype": "Store Debit Note",
			"supplier": pr.supplier,
			"grn": pr.name,
			"gate_entry": pr.get("custom_gate_entry"),
			"posting_date": pr.posting_date,
			"note": pr.get("custom_grn_note"),
			"items": lines,
		}
	)
	note.insert()
	return {"name": note.name, "created": 1}


def _existing_receipt(gate_name):
	draft = frappe.get_all(
		"Purchase Receipt",
		filters={"custom_gate_entry": gate_name, "docstatus": 0, "is_return": 0},
		pluck="name",
		limit=1,
	)
	if draft:
		return draft[0]
	submitted = frappe.get_all(
		"Purchase Receipt",
		filters={"custom_gate_entry": gate_name, "docstatus": 1, "is_return": 0},
		pluck="name",
		order_by="modified desc",
		limit=1,
	)
	return submitted[0] if submitted else None


def _new_receipt(gate):
	if gate.purchase_order:
		po_supplier = frappe.db.get_value("Purchase Order", gate.purchase_order, "supplier")
		if gate.supplier and po_supplier and gate.supplier != po_supplier:
			frappe.throw(
				_("Purchase Order {0} belongs to {1}, not the supplier on this gate entry.").format(
					gate.purchase_order, po_supplier
				)
			)
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

		pr = make_purchase_receipt(gate.purchase_order)
	else:
		pr = frappe.new_doc("Purchase Receipt")
		pr.supplier = gate.supplier
		pr.company = _company()
	pr.custom_gate_entry = gate.name
	pr.custom_arrival_type = gate.arrival_type or "PO"
	pr.custom_typed_po_number = gate.po_number or gate.purchase_order
	if gate.notes:
		pr.custom_grn_note = gate.notes
	_apply_receiving_warehouse(pr)
	if not pr.company:
		pr.company = _company()
	return pr


def _po_items(purchase_order):
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt

	mapped = make_purchase_receipt(purchase_order)
	items = []
	for row in mapped.items:
		items.append(
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": row.qty,
				"rate": row.rate,
				"uom": row.uom,
				"stock_uom": row.stock_uom,
				"conversion_factor": row.conversion_factor or 1,
				"warehouse": row.warehouse,
				"purchase_order": row.purchase_order,
				"purchase_order_item": row.purchase_order_item,
				"custom_ordered_qty": row.qty,
			}
		)
	return items


def _copy_invoice_images(pr, gate):
	existing = {row.image for row in (pr.get("custom_invoice_images") or []) if row.image}
	for row in gate.invoice_photo or []:
		if row.image and row.image not in existing:
			pr.append("custom_invoice_images", {"image": row.image, "source": "Gate Entry"})
			existing.add(row.image)


def _apply_receiving_warehouse(pr):
	from k95_store.stock.utils import get_settings

	warehouse = get_settings().receiving_warehouse
	if not warehouse:
		return
	if not pr.set_warehouse:
		pr.set_warehouse = warehouse
	for row in pr.items:
		if not row.warehouse:
			row.warehouse = warehouse


def _company():
	company = frappe.db.get_single_value("Store Settings", "company") or frappe.defaults.get_global_default(
		"company"
	)
	if not company:
		frappe.throw(_("Set the company in Store Settings before creating a GRN."))
	return company
