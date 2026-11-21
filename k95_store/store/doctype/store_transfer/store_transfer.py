from frappe.model.document import Document

from k95_store.ops.ops import post_transfer


class StoreTransfer(Document):
	def before_insert(self):
		if self.lot_id and not self.item_code:
			import frappe

			self.item_code = frappe.db.get_value("Batch", self.lot_id, "item")

	def on_submit(self):
		post_transfer(self)
		self.db_set(
			{
				"stock_entry": self.stock_entry,
				"status": "completed",
				"transferred_by": self.transferred_by,
				"transferred_at": self.transferred_at,
			}
		)

	def on_cancel(self):
		self.db_set("status", "cancelled")
