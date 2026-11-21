frappe.listview_settings["Gate Entry"] = {
	onload(listview) {
		frappe.call({
			method: "k95_store.inbound.grn_bridge.open_gate_entries_without_grn",
			callback(r) {
				const names = r.message || [];
				listview.page.add_inner_button(__("Open without GRN ({0})", [names.length]), () => {
					listview.filter_area
						.clear()
						.then(() =>
							listview.filter_area.add(
								"Gate Entry",
								"name",
								"in",
								names.length ? names : ["__none__"]
							)
						);
				});
			},
		});
	},
};
