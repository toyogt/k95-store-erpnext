frappe.query_reports["Store Near Expiry"] = {
	filters: [
		{ fieldname: "item_code", label: "Item", fieldtype: "Link", options: "Item" },
		{ fieldname: "days", label: "Days Ahead", fieldtype: "Int", default: 30 },
	],
};
