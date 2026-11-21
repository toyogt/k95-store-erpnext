frappe.ui.form.on("Store Putaway", {
	refresh(frm) {
		frm.set_query("location", "items", () => ({
			filters: {
				disabled: 0,
				is_group: 0,
				custom_location_type: "storage",
			},
		}));
		frm.add_custom_button(__("Load Pending Lots"), () => {
			frappe.call({
				method: "k95_store.api.pending_putaway",
				callback(r) {
					frm.clear_table("items");
					(r.message || []).forEach((row) => {
						frm.add_child("items", {
							lot_id: row.lot_id,
							item_code: row.item_code,
							quantity: row.pending_putaway_qty,
						});
					});
					frm.refresh_field("items");
				},
			});
		});
	},
});
