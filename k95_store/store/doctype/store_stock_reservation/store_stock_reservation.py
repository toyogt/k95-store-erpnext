import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class StoreStockReservation(Document):
	def before_insert(self):
		if not self.reserved_at:
			self.reserved_at = now_datetime()
		if self.location and not self.location_code:
			self.location_code = frappe.db.get_value("Warehouse", self.location, "custom_location_code")


@frappe.whitelist()
def release(name):
	doc = frappe.get_doc("Store Stock Reservation", name)
	if doc.status != "ACTIVE":
		frappe.throw(frappe._("Only ACTIVE reservations can be released."))
	doc.status = "RELEASED"
	doc.save()
	return doc
