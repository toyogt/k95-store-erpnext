if (!window.__k95_gate_entry_form) {
	window.__k95_gate_entry_form = true;

	const EDIT_ROLES = [
		"Guard",
		"Factory Guard",
		"Gate Entry Editor",
		"System Manager",
		"Administrator",
		"Store Manager",
		"Store User",
		"Gate Security",
	];
	const GRN_ROLES = ["System Manager", "Administrator", "Store Manager", "Store User", "Gate Entry Editor"];

	frappe.ui.form.on("Gate Entry", {
		refresh(frm) {
			frm.dashboard.clear_comment();
			frm.dashboard.add_comment(
				__(
					"Arrival evidence only. This does not create stock. Linked GRN, putaway, QC, and debit notes show under Connections."
				),
				"blue",
				true
			);
			_toggle_gate_requirements(frm);
			_show_open_without_grn(frm);
			frm.set_query("purchase_order", () => {
				const filters = {
					docstatus: 1,
					status: ["not in", ["Closed", "Completed", "Cancelled"]],
				};
				if (frm.doc.supplier) {
					filters.supplier = frm.doc.supplier;
				}
				return { filters };
			});
			if (!frm.is_new()) {
				frm.add_custom_button(__("Print"), () => {
					frappe.utils.print(frm.doctype, frm.doc.name, "Gate Entry");
				});
				if (frm.doc.docstatus < 2 && GRN_ROLES.some((role) => frappe.user.has_role(role))) {
					frm.add_custom_button(__("Create GRN"), () => _create_grn(frm));
				}
			}
			if (EDIT_ROLES.some((role) => frappe.user.has_role(role))) {
				_bind_upload(frm, "vehicle_photo", true);
				_bind_upload(frm, "invoice_photo", false);
				_bind_upload(frm, "material_photo", true);
			}
		},
		arrival_type(frm) {
			_toggle_gate_requirements(frm);
		},
		transport_type(frm) {
			_toggle_gate_requirements(frm);
		},
		supplier(frm) {
			if (!frm.doc.supplier) {
				return;
			}
			frappe.db.get_value("Supplier", frm.doc.supplier, "supplier_name").then((r) => {
				if (r.message && r.message.supplier_name) {
					frm.set_value("supplier_name", r.message.supplier_name);
				}
			});
			if (frm.doc.purchase_order) {
				frappe.db.get_value("Purchase Order", frm.doc.purchase_order, "supplier").then((r) => {
					if (r.message && r.message.supplier && r.message.supplier !== frm.doc.supplier) {
						frm.set_value("purchase_order", "");
					}
				});
			}
		},
		purchase_order(frm) {
			if (!frm.doc.purchase_order) {
				return;
			}
			frm.set_value("po_number", frm.doc.purchase_order);
			if (!frm.doc.supplier) {
				frappe.db.get_value("Purchase Order", frm.doc.purchase_order, "supplier").then((r) => {
					if (r.message && r.message.supplier) {
						frm.set_value("supplier", r.message.supplier);
					}
				});
			}
		},
		po_number(frm) {
			const number = (frm.doc.po_number || "").trim();
			if (!number || frm.doc.purchase_order === number) {
				return;
			}
			const filters = { name: number, docstatus: 1 };
			if (frm.doc.supplier) {
				filters.supplier = frm.doc.supplier;
			}
			frappe.db.get_value("Purchase Order", filters, "name").then((r) => {
				if (r.message && r.message.name) {
					frm.set_value("purchase_order", r.message.name);
				}
			});
		},
	});

	function _show_open_without_grn(frm) {
		frappe.call({
			method: "k95_store.inbound.grn_bridge.open_gate_entries_without_grn",
			callback(r) {
				const names = r.message || [];
				frm.dashboard.add_comment(
					__("{0} gate entries are open and have no GRN.", [names.length]),
					names.length ? "orange" : "green",
					true
				);
			},
		});
	}

	function _create_grn(frm) {
		frappe.call({
			method: "k95_store.inbound.grn_bridge.make_purchase_receipt_from_gate_entry",
			args: { gate_entry: frm.doc.name },
			freeze: true,
			freeze_message: __("Creating the GRN"),
			callback(r) {
				if (!r.message || !r.message.name) {
					return;
				}
				if (!r.message.created) {
					frappe.show_alert({
						message: __("Opened the GRN already linked to this gate entry."),
						indicator: "blue",
					});
				}
				frappe.set_route("Form", "Purchase Receipt", r.message.name);
			},
		});
	}

	function _toggle_gate_requirements(frm) {
		const local = frm.doc.arrival_type === "LOCAL";
		const vehicle = frm.doc.transport_type === "vehicle";
		frm.toggle_reqd("vehicle_number", vehicle);
		frm.toggle_reqd("driver_number", vehicle);
		frm.toggle_reqd("vehicle_photo", vehicle);
		frm.toggle_reqd("invoice_photo", !local);
		frm.toggle_reqd("material_photo", true);
	}

	function _bind_upload(frm, fieldname, compress) {
		const field = frm.get_field(fieldname);
		if (!field || !field.grid) {
			return;
		}
		field.grid.add_custom_button(__("Upload Photos"), () => {
			_pick_photos(frm, fieldname, compress);
		});
	}

	function _pick_photos(frm, fieldname, compress) {
		const input = document.createElement("input");
		input.type = "file";
		input.accept = "image/*";
		input.multiple = true;
		input.onchange = async () => {
			const files = Array.from(input.files || []);
			if (!files.length) {
				return;
			}
			frappe.dom.freeze(__("Uploading photos"));
			try {
				for (const file of files) {
					const prepared = compress ? await _compress_image(file) : file;
					const file_url = await _upload_file(prepared);
					const row = frm.add_child(fieldname);
					row.image = file_url;
				}
				frm.refresh_field(fieldname);
				frm.dirty();
			} catch (error) {
				frappe.msgprint(__("Could not upload one of the photos."));
				console.error(error);
			} finally {
				frappe.dom.unfreeze();
			}
		};
		input.click();
	}

	function _compress_image(file) {
		return new Promise((resolve) => {
			const image = new Image();
			const url = URL.createObjectURL(file);
			image.onload = () => {
				const canvas = document.createElement("canvas");
				canvas.width = Math.max(1, Math.round(image.width * 0.5));
				canvas.height = Math.max(1, Math.round(image.height * 0.5));
				canvas.getContext("2d").drawImage(image, 0, 0, canvas.width, canvas.height);
				canvas.toBlob(
					(blob) => {
						URL.revokeObjectURL(url);
						if (!blob) {
							resolve(file);
							return;
						}
						const name = (file.name || "photo").replace(/\.\w+$/, "") + "-c50.jpg";
						resolve(new File([blob], name, { type: "image/jpeg" }));
					},
					"image/jpeg",
					0.8
				);
			};
			image.onerror = () => {
				URL.revokeObjectURL(url);
				resolve(file);
			};
			image.src = url;
		});
	}

	function _upload_file(file) {
		return new Promise((resolve, reject) => {
			const data = new FormData();
			data.append("file", file, file.name);
			data.append("is_private", 1);
			fetch("/api/method/upload_file", {
				method: "POST",
				body: data,
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			})
				.then((response) => response.json())
				.then((payload) => {
					if (!payload.message || !payload.message.file_url) {
						reject(payload);
						return;
					}
					resolve(payload.message.file_url);
				})
				.catch(reject);
		});
	}
}
