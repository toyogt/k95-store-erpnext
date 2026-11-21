frappe.ui.form.on("Warehouse", {
	refresh(frm) {
		if (frm.doc.custom_location_code && !frm.doc.disabled) {
			frm.dashboard.add_comment(__("QR payload is the location code: {0}", [frm.doc.custom_location_code]), "blue", true);
		}
	},
	warehouse_name(frm) {
		if (frm.is_new() && frm.doc.warehouse_name && !frm.doc.custom_location_code && !frm.doc.is_group) {
			frm.set_value("custom_location_code", frm.doc.warehouse_name.replace(/\s+/g, "-").toUpperCase());
		}
	},
});
