import frappe
from frappe import _
from frappe.model.document import Document

from k95_store.outbound.issue import allocate_for_request, create_reservations


class LabellingMaterialRequest(Document):
	def validate(self):
		if self.production_serial:
			duplicate = frappe.db.exists(
				"Labelling Material Request",
				{
					"production_serial": self.production_serial,
					"name": ["!=", self.name],
					"status": ["not in", ["cancelled", "closed"]],
				},
			)
			if duplicate:
				frappe.throw(_("One active labelling request is allowed per production serial."))
		self.revision = frappe.utils.cint(self.revision)

	def issue(self, operation_id=None):
		if operation_id and self.operation_id and operation_id != self.operation_id:
			frappe.throw(_("Stale operation. Reload the request (optimistic lock)."))
		issue = frappe.new_doc("Store Issue")
		issue.issue_type = "production"
		issue.reference_doctype = "Labelling Material Request"
		issue.reference_number = self.name
		for row in self.items:
			allocations = allocate_for_request(row.item_code, row.requested_quantity)
			create_reservations("Labelling Material Request", self.name, allocations, request_line=row.name)
			for alloc in allocations:
				issue.append(
					"items",
					{
						"item_code": alloc.item_code,
						"lot_id": alloc.lot_id,
						"location": alloc.warehouse,
						"requested_quantity": row.requested_quantity,
						"issued_quantity": alloc.quantity,
					},
				)
				row.issued_quantity = frappe.utils.flt(row.issued_quantity) + frappe.utils.flt(alloc.quantity)
		issue.insert(ignore_permissions=True)
		issue.submit()
		self.store_issue = issue.name
		self.status = "issued"
		self.revision = frappe.utils.cint(self.revision) + 1
		self.save()

	def reverse(self):
		frappe.throw(_("Labelling material request reverse is not allowed."))


@frappe.whitelist()
def issue(name, operation_id=None):
	doc = frappe.get_doc("Labelling Material Request", name)
	doc.issue(operation_id=operation_id)
	return doc
