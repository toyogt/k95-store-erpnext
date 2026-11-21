import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, time_diff_in_seconds


class StoreDamageReport(Document):
	def validate(self):
		if not self.reported_at:
			self.reported_at = now_datetime()
		if self.lot_id and not self.item_code:
			self.item_code = frappe.db.get_value("Batch", self.lot_id, "item")
		if not self.gate_entry and self.lot_id:
			self.gate_entry = frappe.db.get_value("Batch", self.lot_id, "custom_gate_entry")
		if not self.gate_entry and self.grn:
			self.gate_entry = frappe.db.get_value("Purchase Receipt", self.grn, "custom_gate_entry")

		if self.source == "issue":
			if not self.issue:
				frappe.throw(_("Store Issue is required for an issue damage report."))
			issued_at = frappe.db.get_value("Store Issue", self.issue, "issued_at")
			if not issued_at:
				frappe.throw(_("Stock issue {0} has no issued time.").format(self.issue))
			self.is_within_window = 1 if time_diff_in_seconds(self.reported_at, get_datetime(issued_at)) <= 2 * 3600 else 0
			if not self.is_within_window:
				frappe.throw(_("Damage reports against an issue are allowed only within 2 hours of the stock issue."))
			return

		self.is_within_window = 1
		if not self.lot_id:
			frappe.throw(_("Lot is required for inbound or QC damage."))
