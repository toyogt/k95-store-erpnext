import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from k95_store.inbound.putaway import get_pending, post_putaway


class StorePutaway(Document):
	def validate(self):
		if not self.putaway_by:
			self.putaway_by = frappe.session.user
		if not self.putaway_at:
			self.putaway_at = now_datetime()
		_link_gate_and_grn(self)

	def on_submit(self):
		post_putaway(self)
		self.db_set("status", "posted")
		self.db_set("stock_entry", self.stock_entry)


def _link_gate_and_grn(doc):
	gates = set()
	grns = set()
	for row in doc.items or []:
		if not row.lot_id:
			continue
		gate, grn = frappe.db.get_value("Batch", row.lot_id, ["custom_gate_entry", "custom_grn"]) or (None, None)
		if gate:
			gates.add(gate)
		if grn:
			grns.add(grn)
	if not doc.gate_entry and len(gates) == 1:
		doc.gate_entry = next(iter(gates))
	if not doc.grn and len(grns) == 1:
		doc.grn = next(iter(grns))


@frappe.whitelist()
def pending_queue():
	return get_pending()
