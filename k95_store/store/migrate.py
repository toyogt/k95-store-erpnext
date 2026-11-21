import json
import os

import frappe


SNAPSHOT = "gate_entry_photo_migration.json"
PHOTO_FIELDS = ("vehicle_photo", "invoice_photo", "material_photo")


def snapshot_gate_photos():
	"""Keep single-attach photo paths before those columns become child tables."""
	if not frappe.db.table_exists("Gate Entry"):
		return
	columns = set(frappe.db.get_table_columns("Gate Entry"))
	if "vehicle_photo" not in columns:
		return
	rows = frappe.db.sql(
		"""
		select name, vehicle_photo, invoice_photo, material_photo
		from `tabGate Entry`
		where ifnull(vehicle_photo, '') != ''
			or ifnull(invoice_photo, '') != ''
			or ifnull(material_photo, '') != ''
		""",
		as_dict=True,
	)
	path = _snapshot_path()
	os.makedirs(os.path.dirname(path), exist_ok=True)
	with open(path, "w", encoding="utf-8") as handle:
		json.dump(rows, handle)


def restore_gate_photos():
	_restore_snapshot()
	_move_extra_photos()


def clear_gate_photo_snapshot():
	path = _snapshot_path()
	if os.path.exists(path):
		os.remove(path)


def backfill_gate_links():
	_backfill_gate_audit()
	_backfill_putaway()
	_backfill_damage()
	_backfill_quality_inspections()


def _snapshot_path():
	return frappe.get_site_path("private", SNAPSHOT)


def _restore_snapshot():
	path = _snapshot_path()
	if not os.path.exists(path) or not frappe.db.table_exists("Gate Entry Photo"):
		return
	with open(path, encoding="utf-8") as handle:
		rows = json.load(handle)
	for row in rows:
		for fieldname in PHOTO_FIELDS:
			url = row.get(fieldname)
			if not url or not isinstance(url, str) or url.startswith("["):
				continue
			_ensure_photo_row(row["name"], fieldname, url)


def _move_extra_photos():
	if not frappe.db.table_exists("Gate Entry Photo"):
		return
	if not frappe.db.has_column("Gate Entry Photo", "slot"):
		return
	frappe.db.sql(
		"""
		update `tabGate Entry Photo`
		set parentfield = case
			when slot = 'vehicle' then 'vehicle_photo'
			when slot = 'invoice' then 'invoice_photo'
			else 'material_photo'
		end
		where parenttype = 'Gate Entry'
			and parentfield = 'photos'
		"""
	)


def _ensure_photo_row(parent, parentfield, file_url):
	if frappe.db.exists(
		"Gate Entry Photo",
		{"parent": parent, "parenttype": "Gate Entry", "parentfield": parentfield, "image": file_url},
	):
		return
	idx = frappe.db.count("Gate Entry Photo", {"parent": parent, "parentfield": parentfield}) + 1
	child = frappe.get_doc(
		{
			"doctype": "Gate Entry Photo",
			"parent": parent,
			"parenttype": "Gate Entry",
			"parentfield": parentfield,
			"image": file_url,
			"idx": idx,
		}
	)
	child.insert(ignore_permissions=True, ignore_mandatory=True)


def _backfill_gate_audit():
	if not frappe.db.table_exists("Gate Entry"):
		return
	if not frappe.db.has_column("Gate Entry", "submitted_by_email"):
		return
	rows = frappe.db.sql(
		"""
		select name, owner, submitted_by_email, submitted_by_name
		from `tabGate Entry`
		where ifnull(submitted_by_email, '') = ''
			or ifnull(submitted_by_name, '') = ''
		""",
		as_dict=True,
	)
	for row in rows:
		values = {}
		user = row.owner or "Administrator"
		if not row.submitted_by_email:
			values["submitted_by_email"] = user
		if not row.submitted_by_name:
			values["submitted_by_name"] = frappe.db.get_value("User", user, "full_name") or user
		if values:
			frappe.db.set_value("Gate Entry", row.name, values, update_modified=False)


def _backfill_putaway():
	if not frappe.db.has_column("Store Putaway", "gate_entry"):
		return
	names = frappe.db.sql(
		"""
		select name from `tabStore Putaway`
		where ifnull(gate_entry, '') = '' or ifnull(grn, '') = ''
		""",
		pluck=True,
	)
	for name in names:
		items = frappe.get_all("Store Putaway Item", filters={"parent": name}, fields=["lot_id"])
		gate, grn = _single_gate_and_grn(row.lot_id for row in items)
		current = frappe.db.get_value("Store Putaway", name, ["gate_entry", "grn"], as_dict=True)
		values = {}
		if gate and not current.gate_entry:
			values["gate_entry"] = gate
		if grn and not current.grn:
			values["grn"] = grn
		if values:
			frappe.db.set_value("Store Putaway", name, values, update_modified=False)


def _backfill_damage():
	if not frappe.db.has_column("Store Damage Report", "gate_entry"):
		return
	rows = frappe.db.sql(
		"""
		select name, lot_id, grn
		from `tabStore Damage Report`
		where ifnull(gate_entry, '') = ''
		""",
		as_dict=True,
	)
	for row in rows:
		gate = None
		if row.lot_id:
			gate = frappe.db.get_value("Batch", row.lot_id, "custom_gate_entry")
		if not gate and row.grn:
			gate = frappe.db.get_value("Purchase Receipt", row.grn, "custom_gate_entry")
		if gate:
			frappe.db.set_value("Store Damage Report", row.name, "gate_entry", gate, update_modified=False)


def _backfill_quality_inspections():
	if not frappe.db.table_exists("Quality Inspection"):
		return
	if not frappe.db.has_column("Quality Inspection", "custom_gate_entry"):
		return
	rows = frappe.db.sql(
		"""
		select name, reference_type, reference_name, batch_no
		from `tabQuality Inspection`
		where ifnull(custom_gate_entry, '') = ''
		""",
		as_dict=True,
	)
	for row in rows:
		gate = _gate_for_inspection(row.reference_type, row.reference_name, row.batch_no)
		if gate:
			frappe.db.set_value("Quality Inspection", row.name, "custom_gate_entry", gate, update_modified=False)


def _single_gate_and_grn(lot_ids):
	gates = set()
	grns = set()
	for lot_id in lot_ids:
		if not lot_id:
			continue
		gate, grn = frappe.db.get_value("Batch", lot_id, ["custom_gate_entry", "custom_grn"]) or (None, None)
		if gate:
			gates.add(gate)
		if grn:
			grns.add(grn)
	return (next(iter(gates)) if len(gates) == 1 else None, next(iter(grns)) if len(grns) == 1 else None)


def _gate_for_inspection(reference_type, reference_name, batch_no):
	gate = None
	if reference_type == "Purchase Receipt" and reference_name:
		gate = frappe.db.get_value("Purchase Receipt", reference_name, "custom_gate_entry")
	if not gate and batch_no:
		gate = frappe.db.get_value("Batch", batch_no, "custom_gate_entry")
	return gate
