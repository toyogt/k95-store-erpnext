import frappe
from frappe import _
from frappe.model.document import Document

from k95_store.ops.ops import post_adjustment


class StoreAdjustment(Document):
	def validate(self):
		if not (self.reason or "").strip():
			frappe.throw(_("Reason is required."))

	def on_submit(self):
		post_adjustment(self)
		self.db_set("status", self.status)
		if self.stock_reconciliation:
			self.db_set("stock_reconciliation", self.stock_reconciliation)

	def on_cancel(self):
		self.db_set("status", "rejected")
