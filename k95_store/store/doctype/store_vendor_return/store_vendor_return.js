frappe.ui.form.on("Store Vendor Return", {
	refresh(frm) {
		frm.set_query("location", "items", () => ({
			filters: {
				disabled: 0,
				is_group: 0,
				custom_location_type: ["in", ["storage", "rejected"]],
			},
		}));
		if (frm.doc.status === "draft") {
			frm.add_custom_button(__("Submit Request"), () => act("submit_request", frm));
		}
		if (frm.doc.status === "submitted") {
			frm.add_custom_button(__("Approve"), () => act("approve", frm));
		}
		if (frm.doc.status === "approved") {
			frm.add_custom_button(__("Post Return"), () => act("post", frm));
		}
	},
});

function act(fn, frm) {
	frappe.call({
		method: `k95_store.store.doctype.store_vendor_return.store_vendor_return.${fn}`,
		args: { name: frm.doc.name },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
