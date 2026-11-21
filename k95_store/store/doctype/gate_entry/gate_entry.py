import base64
import re
from io import BytesIO

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


COMPRESS_FIELDS = ("vehicle_photo", "material_photo")
PHOTO_FIELDS = ("vehicle_photo", "invoice_photo", "material_photo")


class GateEntry(Document):
	def validate(self):
		_fill_submitter(self)
		if not self.arrived_at:
			self.arrived_at = now_datetime()
		if not self.workflow_state:
			self.workflow_state = "Draft"
		_normalize_arrival(self)
		_fill_party(self)
		_compress_photos(self)
		validate_gate_entry(self)

	def on_trash(self):
		if self.status == "CLOSED":
			frappe.throw(_("Cannot delete a closed gate entry."))
		if frappe.db.exists("Purchase Receipt", {"custom_gate_entry": self.name, "docstatus": 1, "is_return": 0}):
			frappe.throw(_("Cannot delete gate entry {0} because a received GRN points at it.").format(self.name))

	def photo_src(self, file_url):
		"""Return a data URI so the print format can show private photos."""
		if not file_url:
			return ""
		try:
			file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
			if not file_name:
				return file_url
			content = frappe.get_doc("File", file_name).get_content()
			encoded = base64.b64encode(content).decode()
			return f"data:image/jpeg;base64,{encoded}"
		except Exception:
			return file_url


def validate_gate_entry(doc):
	arrival = (doc.arrival_type or "PO").strip().upper()
	local = arrival == "LOCAL"
	vehicle = doc.transport_type == "vehicle"

	if vehicle:
		if not (doc.vehicle_number or "").strip():
			frappe.throw(_("Vehicle number is required for vehicle transport."))
		if not doc.driver_number or not re.fullmatch(r"[6-9]\d{9}", str(doc.driver_number).strip()):
			frappe.throw(_("Driver mobile must be an Indian 10-digit number starting 6-9."))
	elif doc.driver_number and not re.fullmatch(r"[6-9]\d{9}", str(doc.driver_number).strip()):
		frappe.throw(_("Driver mobile must be an Indian 10-digit number starting 6-9."))

	if vehicle and not _image_count(doc, "vehicle_photo"):
		frappe.throw(_("Vehicle photo is required."))
	if not _image_count(doc, "material_photo"):
		frappe.throw(_("Material photo is required."))
	if not local and not _image_count(doc, "invoice_photo"):
		frappe.throw(_("Invoice or challan photo is required."))


def _image_count(doc, fieldname):
	return sum(1 for row in (doc.get(fieldname) or []) if row.image)


def _normalize_arrival(doc):
	raw = (doc.arrival_type or "PO").strip()
	key = raw.upper()
	if key == "PO":
		doc.arrival_type = "PO"
	elif key == "INVOICE":
		doc.arrival_type = "Invoice"


def _fill_submitter(doc):
	user = frappe.session.user
	if not user or user == "Guest":
		return
	if not doc.submitted_by_email:
		doc.submitted_by_email = user
	if not doc.submitted_by_name:
		doc.submitted_by_name = frappe.db.get_value("User", user, "full_name") or user


def _fill_party(doc):
	typed = (doc.po_number or "").strip()
	if typed and not doc.purchase_order:
		filters = {"name": typed, "docstatus": 1}
		if doc.supplier:
			filters["supplier"] = doc.supplier
		if frappe.db.exists("Purchase Order", filters):
			doc.purchase_order = typed
	if doc.purchase_order:
		po_supplier = frappe.db.get_value("Purchase Order", doc.purchase_order, "supplier")
		if po_supplier and doc.supplier and po_supplier != doc.supplier:
			frappe.throw(
				_("Purchase Order {0} belongs to {1}, not {2}.").format(
					doc.purchase_order, po_supplier, doc.supplier
				)
			)
		if po_supplier and not doc.supplier:
			doc.supplier = po_supplier
		if not doc.po_number:
			doc.po_number = doc.purchase_order
	if doc.supplier and not doc.supplier_name:
		doc.supplier_name = frappe.db.get_value("Supplier", doc.supplier, "supplier_name") or doc.supplier


def _compress_photos(doc):
	previous = {}
	if getattr(doc, "_doc_before_save", None):
		for fieldname in COMPRESS_FIELDS:
			for row in doc._doc_before_save.get(fieldname) or []:
				previous[row.get("name")] = row.get("image")
	for fieldname in COMPRESS_FIELDS:
		for row in doc.get(fieldname) or []:
			if row.name and previous.get(row.name) and previous.get(row.name) != row.image:
				row.compressed = 0
			if not row.image or row.compressed or "-c50" in row.image:
				if row.image and "-c50" in row.image:
					row.compressed = 1
				continue
			row.image = _compress_file(row.image)
			row.compressed = 1


def _compress_file(file_url):
	try:
		from PIL import Image, ImageOps
	except ImportError:
		return file_url

	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		return file_url
	file_doc = frappe.get_doc("File", file_name)
	try:
		image = Image.open(BytesIO(file_doc.get_content()))
		image = ImageOps.exif_transpose(image)
		if image.mode != "RGB":
			image = image.convert("RGB")
		resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
		image = image.resize(
			(max(1, int(image.width * 0.5)), max(1, int(image.height * 0.5))),
			resample,
		)
		buffer = BytesIO()
		image.save(buffer, format="JPEG", quality=80, optimize=True)
		base = (file_doc.file_name or "photo").rsplit(".", 1)[0]
		compressed = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"{base}-c50.jpg",
				"is_private": 1,
				"content": buffer.getvalue(),
			}
		)
		compressed.save(ignore_permissions=True)
		return compressed.file_url
	except Exception:
		frappe.log_error(title="Gate entry photo compress")
		return file_url
