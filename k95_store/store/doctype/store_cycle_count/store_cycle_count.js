frappe.ui.form.on("Store Cycle Count", {
	refresh(frm) {
		if (frm.doc.status === "counted") {
			frm.add_custom_button(__("Approve"), () => {
				frappe.call({
					method: "k95_store.store.doctype.store_cycle_count.store_cycle_count.approve",
					args: { name: frm.doc.name },
					callback: () => frm.reload_doc(),
				});
			});
		}
		if (frm.doc.status === "approved") {
			frm.add_custom_button(__("Apply"), () => {
				frappe.call({
					method: "k95_store.store.doctype.store_cycle_count.store_cycle_count.apply",
					args: { name: frm.doc.name },
					freeze: true,
					callback: () => frm.reload_doc(),
				});
			});
		}
	},
});
