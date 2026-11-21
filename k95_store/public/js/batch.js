frappe.ui.form.on("Batch", {
	refresh(frm) {
		if (!frm.doc.name) {
			return;
		}
		if (frm.doc.custom_lot_status === "pending_qc") {
			frm.add_custom_button(
				__("Pass QC"),
				() => {
					frappe.call({
						method: "k95_store.api.pass_qc",
						args: { batch_no: frm.doc.name },
						callback: () => frm.reload_doc(),
					});
				},
				__("Store")
			);
			frm.add_custom_button(
				__("Fail QC"),
				() => {
					frappe.prompt(
						{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
						(values) => {
							frappe.call({
								method: "k95_store.api.fail_qc",
								args: { batch_no: frm.doc.name, reason: values.reason },
								callback: () => frm.reload_doc(),
							});
						}
					);
				},
				__("Store")
			);
		}
		["rejected", "damaged"].forEach((status) => {
			frm.add_custom_button(
				__(status === "rejected" ? "Hold as Rejected" : "Hold as Damaged"),
				() => {
					frappe.prompt(
						{ fieldname: "reason", fieldtype: "Small Text", label: __("Reason"), reqd: 1 },
						(values) => {
							frappe.call({
								method: "k95_store.api.hold_lot",
								args: { batch_no: frm.doc.name, status, reason: values.reason },
								callback: () => frm.reload_doc(),
							});
						}
					);
				},
				__("Store")
			);
		});
	},
});
