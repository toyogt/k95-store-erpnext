frappe.query_reports["Store Stock Balance"] = {
	filters: [
		{ fieldname: "item_code", label: "Item", fieldtype: "Link", options: "Item" },
		{ fieldname: "lot_id", label: "Lot", fieldtype: "Link", options: "Batch" },
		{ fieldname: "include_receiving", label: "Include Pending Putaway", fieldtype: "Check" },
	],
};
