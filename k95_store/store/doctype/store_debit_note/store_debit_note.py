import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class StoreDebitNote(Document):
	def validate(self):
		total = 0
		for row in self.items:
			row.amount = (flt(row.short_qty) + flt(row.rejected_qty)) * flt(row.rate)
			total += flt(row.amount)
		self.total = total
		if not self.items:
			frappe.throw(_("Add at least one line."))
