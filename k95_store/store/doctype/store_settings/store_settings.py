from frappe.model.document import Document


class StoreSettings(Document):
	def on_update(self):
		from k95_store.schema import ensure_warehouse_tree

		ensure_warehouse_tree()
