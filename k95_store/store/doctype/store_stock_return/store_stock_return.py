import frappe
from frappe import _
from frappe.model.document import Document

from k95_store.outbound.returns import post_stock_return, should_auto_approve, validate_stock_return


class StoreStockReturn(Document):
	def validate(self):
		validate_stock_return(self)
		if self.status == "draft" and should_auto_approve(self):
			self.approval_mode = "auto"

	def submit_request(self):
		self.status = "submitted"
		if should_auto_approve(self):
			self.status = "approved"
			self.approval_mode = "auto"
		self.save()

	def approve(self):
		self.status = "approved"
		self.approval_mode = "manager" if self.return_type in ("damaged", "quality_reject") else self.approval_mode
		self.save()

	def post(self):
		if self.status == "draft":
			self.submit_request()
		if self.status == "submitted":
			self.approve()
		post_stock_return(self)
		self.save()


@frappe.whitelist()
def submit_request(name):
	doc = frappe.get_doc("Store Stock Return", name)
	doc.submit_request()
	return doc


@frappe.whitelist()
def approve(name):
	frappe.only_for(("Store Manager", "System Manager"))
	doc = frappe.get_doc("Store Stock Return", name)
	doc.approve()
	return doc


@frappe.whitelist()
def post(name, posting_location=None):
	doc = frappe.get_doc("Store Stock Return", name)
	if posting_location:
		doc.posting_location = posting_location
	doc.post()
	return doc
