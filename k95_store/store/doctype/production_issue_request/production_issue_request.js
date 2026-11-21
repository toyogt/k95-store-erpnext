frappe.ui.form.on("Production Issue Request", {
	refresh(frm) {
		frm.add_custom_button(__("Send to Store"), () => act("send_to_store", frm), __("Store"));
		frm.add_custom_button(__("Start Picking"), () => act("start_picking", frm), __("Store"));
		frm.add_custom_button(__("Issue"), () => act("issue_to_production", frm), __("Store"));
	},
});

function act(fn, frm) {
	frappe.call({
		method: `k95_store.store.doctype.production_issue_request.production_issue_request.${fn}`,
		args: { name: frm.doc.name },
		freeze: true,
		callback: () => frm.reload_doc(),
	});
}
