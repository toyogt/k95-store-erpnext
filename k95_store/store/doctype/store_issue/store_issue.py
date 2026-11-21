import frappe
from frappe.model.document import Document

from k95_store.outbound.issue import post_issue
from k95_store.stock.picker import suggest_issue_allocations


class StoreIssue(Document):
	def on_submit(self):
		post_issue(self)
		self.db_set(
			{
				"stock_entry": self.stock_entry,
				"issued_at": self.issued_at,
				"issued_by": self.issued_by,
				"status": "confirmed",
			}
		)

	def on_cancel(self):
		self.db_set("status", "cancelled")


@frappe.whitelist()
def suggest_allocations(item_code, qty, warehouse=None):
	return suggest_issue_allocations(item_code, qty, warehouse=warehouse)
