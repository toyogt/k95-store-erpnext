frappe.ui.form.on("Item", {
	refresh(frm) {
		if (frm.doc.custom_store_item && !frm.doc.has_batch_no) {
			frm.set_df_property(
				"has_batch_no",
				"description",
				__("Store lots require batch tracking. Lot id is LOT-..., supplier batch is a separate field.")
			);
		}
		if (frm.doc.custom_qc_required) {
			frm.dashboard.add_comment(
				__("QC required: GRN will create a pending_qc lot. It cannot be put away to storage until QC is passed on the Batch."),
				"orange",
				true
			);
		}
	},
	custom_store_item(frm) {
		if (frm.doc.custom_store_item) {
			frm.set_value("is_stock_item", 1);
			frm.set_value("has_batch_no", 1);
			frm.set_value("create_new_batch", 0);
		}
	},
});
