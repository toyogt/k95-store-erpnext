import frappe
from frappe import _
from frappe.model.document import Document


class AIModelKey(Document):
	def validate(self):
		if not self.priority:
			self.priority = 1
		self.model = (self.model or "").strip()
		if not self.model:
			frappe.throw(_("Model is required. Example: gemini-2.0-flash"))
