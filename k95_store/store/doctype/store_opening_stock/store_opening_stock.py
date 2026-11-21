from frappe.model.document import Document

from k95_store.ops.opening import post_opening


class StoreOpeningStock(Document):
	def on_submit(self):
		post_opening(self)
		self.db_set(
			{
				"lot_id": self.lot_id,
				"stock_entry": self.stock_entry,
				"status": "posted",
				"posted_at": self.posted_at,
				"entered_by": self.entered_by,
			}
		)

	def on_cancel(self):
		self.db_set("status", "pending")
