frappe.ui.form.on("Store Issue", {
	refresh(frm) {
		frm.add_custom_button(__("Suggest FEFO"), () => {
			const item = frm.doc.items && frm.doc.items[0];
			if (!item || !item.item_code) {
				frappe.msgprint(__("Add an item first."));
				return;
			}
			frappe.call({
				method: "k95_store.api.suggest_issue",
				args: { item_code: item.item_code, qty: item.requested_quantity || item.issued_quantity || 1 },
				callback(r) {
					frm.clear_table("items");
					(r.message || []).forEach((row) => {
						frm.add_child("items", {
							item_code: row.item_code,
							lot_id: row.lot_id,
							location: row.warehouse,
							issued_quantity: row.quantity,
						});
					});
					frm.refresh_field("items");
				},
			});
		});
	},
});
