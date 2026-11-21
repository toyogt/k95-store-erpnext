frappe.ui.form.on("Store Stock Return", {
	refresh(frm) {
		if (frm.doc.status === "draft") {
			frm.add_custom_button(__("Submit Request"), () => call("submit_request", frm));
		}
		if (frm.doc.status === "submitted") {
			frm.add_custom_button(__("Approve"), () => call("approve", frm));
		}
		if (["draft", "submitted", "approved"].includes(frm.doc.status)) {
			frm.add_custom_button(__("Post to Store"), () => {
				if (!frm.doc.posting_location) {
					frappe.msgprint(__("Choose a return location first."));
					return;
				}
				call("post", frm);
			});
		}
	},
});

function call(fn, frm) {
	frappe.call({
		method: `k95_store.store.doctype.store_stock_return.store_stock_return.${fn}`,
		args: { name: frm.doc.name, posting_location: frm.doc.posting_location },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
