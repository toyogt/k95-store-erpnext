import frappe
from frappe.model.document import Document
from frappe.utils import flt

from k95_store.ops.ops import apply_cycle_count


class StoreCycleCount(Document):
	def validate(self):
		from erpnext.stock.doctype.batch.batch import get_batch_qty

		for row in self.items:
			row.system_quantity = flt(get_batch_qty(row.lot_id, row.location) or 0)
			row.variance = flt(row.physical_quantity) - flt(row.system_quantity)
			if not row.item_code and row.lot_id:
				row.item_code = frappe.db.get_value("Batch", row.lot_id, "item")
		if self.status == "pending" and self.items:
			self.status = "counted"

	def approve(self):
		frappe.only_for(("Store Manager", "System Manager"))
		self.status = "approved"
		self.save()

	def apply(self):
		if self.status != "approved":
			self.approve()
		apply_cycle_count(self)
		self.save()


@frappe.whitelist()
def approve(name):
	doc = frappe.get_doc("Store Cycle Count", name)
	doc.approve()
	return doc


@frappe.whitelist()
def apply(name):
	doc = frappe.get_doc("Store Cycle Count", name)
	doc.apply()
	return doc
