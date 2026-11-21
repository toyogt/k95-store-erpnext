import frappe
from frappe.model.document import Document

from k95_store.inbound.charges import post_later_charge


class StoreGRNCharge(Document):
	pass


@frappe.whitelist()
def post_pending(grn, charge_type, amount, party_name=None, bilty_number=None):
	return post_later_charge(grn, charge_type, amount, party_name=party_name, bilty_number=bilty_number)
