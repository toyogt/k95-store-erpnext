import frappe
from frappe.model.document import Document

from k95_store.outbound.returns import post_vendor_return, validate_vendor_return


class StoreVendorReturn(Document):
	def validate(self):
		validate_vendor_return(self)

	def submit_request(self):
		self.status = "submitted"
		self.save()

	def approve(self):
		self.status = "approved"
		self.save()

	def post(self):
		if self.status != "approved":
			frappe.throw(frappe._("Manager approval is required."))
		post_vendor_return(self)
		self.save()


@frappe.whitelist()
def submit_request(name):
	doc = frappe.get_doc("Store Vendor Return", name)
	doc.submit_request()
	return doc


@frappe.whitelist()
def approve(name):
	frappe.only_for(("Store Manager", "System Manager"))
	doc = frappe.get_doc("Store Vendor Return", name)
	doc.approve()
	return doc


@frappe.whitelist()
def post(name):
	doc = frappe.get_doc("Store Vendor Return", name)
	doc.post()
	return doc
