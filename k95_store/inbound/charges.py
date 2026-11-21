import frappe
from frappe.utils import flt, nowdate


def create_landed_cost_if_needed(purchase_receipt):
	freight_option = purchase_receipt.get("custom_freight_option") or "NONE"
	unloading_option = purchase_receipt.get("custom_unloading_option") or "NONE"
	freight = flt(purchase_receipt.get("custom_freight_amount"))
	unloading = flt(purchase_receipt.get("custom_unloading_amount"))

	if freight_option == "EXTRA_LATER" or unloading_option == "EXTRA_LATER":
		_write_pending_charge(purchase_receipt, "FREIGHT", freight, freight_option)
		_write_pending_charge(purchase_receipt, "UNLOADING", unloading, unloading_option)

	now_charges = []
	if freight_option == "EXTRA_NOW" and freight:
		now_charges.append(("FREIGHT", freight))
	if unloading_option == "EXTRA_NOW" and unloading:
		now_charges.append(("UNLOADING", unloading))
	if not now_charges:
		return

	basis = "Amount" if (purchase_receipt.get("custom_allocation_basis") or "VALUE") == "VALUE" else "Qty"
	lcv = frappe.new_doc("Landed Cost Voucher")
	lcv.company = purchase_receipt.company
	lcv.distribute_charges_based_on = basis
	lcv.append(
		"purchase_receipts",
		{
			"receipt_document_type": "Purchase Receipt",
			"receipt_document": purchase_receipt.name,
			"supplier": purchase_receipt.supplier,
			"grand_total": purchase_receipt.grand_total,
		},
	)
	for charge_type, amount in now_charges:
		account = _charge_account(purchase_receipt.company)
		lcv.append(
			"taxes",
			{
				"description": charge_type.title(),
				"expense_account": account,
				"amount": amount,
			},
		)
	lcv.get_items_from_purchase_receipts()
	lcv.insert(ignore_permissions=True)
	lcv.submit()
	for charge_type, amount in now_charges:
		_write_charge_row(purchase_receipt, charge_type, amount, "GRN_RECEIVE", "PENDING")


def post_later_charge(grn, charge_type, amount, party_name=None, bilty_number=None):
	pr = frappe.get_doc("Purchase Receipt", grn)
	account = _charge_account(pr.company)
	basis = "Amount" if (pr.get("custom_allocation_basis") or "VALUE") == "VALUE" else "Qty"
	lcv = frappe.new_doc("Landed Cost Voucher")
	lcv.company = pr.company
	lcv.distribute_charges_based_on = basis
	lcv.append(
		"purchase_receipts",
		{
			"receipt_document_type": "Purchase Receipt",
			"receipt_document": pr.name,
			"supplier": pr.supplier,
			"grand_total": pr.grand_total,
		},
	)
	lcv.append("taxes", {"description": charge_type.title(), "expense_account": account, "amount": amount})
	lcv.get_items_from_purchase_receipts()
	lcv.insert(ignore_permissions=True)
	lcv.submit()
	return _write_charge_row(pr, charge_type, amount, "POST_GRN", "PENDING", party_name, bilty_number)


def _write_pending_charge(purchase_receipt, charge_type, amount, option):
	if option != "EXTRA_LATER" or not amount:
		return
	_write_charge_row(purchase_receipt, charge_type, amount, "GRN_RECEIVE", "PENDING")


def _write_charge_row(purchase_receipt, charge_type, amount, source, payment_status, party_name=None, bilty_number=None):
	if frappe.db.exists(
		"Store GRN Charge",
		{"grn": purchase_receipt.name, "charge_type": charge_type, "source": source, "amount": amount},
	):
		return
	doc = frappe.get_doc(
		{
			"doctype": "Store GRN Charge",
			"grn": purchase_receipt.name,
			"invoice_number": purchase_receipt.get("bill_no"),
			"charge_type": charge_type,
			"amount": amount,
			"charge_date": nowdate(),
			"payment_status": payment_status,
			"source": source,
			"party_name": party_name,
			"bilty_number": bilty_number,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc


def _charge_account(company):
	settings = frappe.get_single("Store Settings")
	if settings.landed_cost_account:
		return settings.landed_cost_account
	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Expense Account", "is_group": 0},
		"name",
	)
	if not account:
		frappe.throw(frappe._("Set Landed Cost Account in Store Settings."))
	return account
