import frappe
from frappe import _
from frappe.model.document import Document

from k95_store.outbound.issue import allocate_for_request, create_reservations


class ProductionIssueRequest(Document):
	def validate(self):
		if self.production_serial:
			duplicate = frappe.db.exists(
				"Production Issue Request",
				{
					"production_serial": self.production_serial,
					"name": ["!=", self.name],
					"status": ["not in", ["cancelled", "deleted", "closed"]],
				},
			)
			if duplicate:
				frappe.throw(_("An active production issue request already exists for serial {0}.").format(self.production_serial))

	def send_to_store(self):
		self.status = "sent_to_store"
		self.save()

	def start_picking(self):
		self.status = "picking"
		for row in self.items:
			needed = frappe.utils.flt(row.issue_quantity or row.requested_quantity)
			allocations = allocate_for_request(row.item_code, needed)
			row.lot_allocations = frappe.as_json(allocations)
			create_reservations("Production Issue Request", self.name, allocations, request_line=row.name)
		self.status = "picking_done"
		self.save()

	def issue_to_production(self):
		if self.status not in ("picking_done", "accepted", "sent_to_store"):
			if self.status == "draft":
				self.send_to_store()
			self.start_picking()
		issue = frappe.new_doc("Store Issue")
		issue.issue_type = "production"
		issue.reference_doctype = "Production Issue Request"
		issue.reference_number = self.name
		for row in self.items:
			allocations = frappe.parse_json(row.lot_allocations or "[]")
			for alloc in allocations:
				issue.append(
					"items",
					{
						"item_code": alloc.get("item_code") or row.item_code,
						"lot_id": alloc.get("lot_id"),
						"location": alloc.get("warehouse"),
						"requested_quantity": row.requested_quantity,
						"issued_quantity": alloc.get("quantity"),
					},
				)
				row.issued_quantity = frappe.utils.flt(row.issued_quantity) + frappe.utils.flt(alloc.get("quantity"))
		issue.insert(ignore_permissions=True)
		issue.submit()
		self.store_issue = issue.name
		self.status = "issued"
		self.save()


@frappe.whitelist()
def send_to_store(name):
	doc = frappe.get_doc("Production Issue Request", name)
	doc.send_to_store()
	return doc


@frappe.whitelist()
def start_picking(name):
	doc = frappe.get_doc("Production Issue Request", name)
	doc.start_picking()
	return doc


@frappe.whitelist()
def issue_to_production(name):
	doc = frappe.get_doc("Production Issue Request", name)
	doc.issue_to_production()
	return doc
