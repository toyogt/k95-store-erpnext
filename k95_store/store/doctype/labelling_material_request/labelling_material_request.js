frappe.ui.form.on("Labelling Material Request", {
	refresh(frm) {
		frm.add_custom_button(__("Issue"), () => {
			frappe.call({
				method: "k95_store.store.doctype.labelling_material_request.labelling_material_request.issue",
				args: { name: frm.doc.name, operation_id: frm.doc.operation_id },
				freeze: true,
				callback: () => frm.reload_doc(),
			});
		});
	},
});
