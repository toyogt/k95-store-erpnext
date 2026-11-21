frappe.ui.form.on("Purchase Receipt", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.set_warehouse) {
			frappe.db.get_single_value("Store Settings", "receiving_warehouse").then((wh) => {
				if (wh && frm.is_new() && !frm.doc.set_warehouse) {
					frm.set_value("set_warehouse", wh);
				}
			});
		}
	},
	refresh(frm) {
		frm.dashboard.clear_comment();
		frm.dashboard.add_comment(
			__(
				"Accepted qty goes to Receiving and is not issuable until Store Putaway. Rejected qty becomes a rejected lot. Linked documents show under Connections."
			),
			"blue",
			true
		);
		if (frm.doc.custom_value_flag) {
			frm.dashboard.add_comment(
				__(
					"Invoice total and GRN value differ by {0}. A difference above ₹2 is flagged.",
					[format_currency(Math.abs(frm.doc.custom_value_difference || 0))]
				),
				"red",
				true
			);
		}
		frm.set_query("custom_gate_entry", () => ({
			filters: { status: "OPEN" },
		}));
		_apply_arrival_rules(frm);
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Get Items from Gate Entry"), () => _pull_gate_entry(frm), __("Store"));
			frm.add_custom_button(__("Copy Invoice Images"), () => _copy_invoice_images(frm), __("Store"));
			frm.add_custom_button(__("Read Invoice"), () => _read_invoice(frm), __("Store"));
			_bind_invoice_upload(frm);
		}
		if (!frm.is_new() && _has_qty_claim(frm)) {
			frm.add_custom_button(__("Create Debit Note"), () => _create_debit_note(frm), __("Store"));
		}
		if (frappe.user.has_role("System Manager") || frappe.user.has_role("Store Manager")) {
			frm.add_custom_button(__("AI Model Keys"), () => frappe.set_route("List", "AI Model Key"), __("Store"));
		}
	},
	custom_gate_entry(frm) {
		if (!frm.doc.custom_gate_entry) {
			frm.set_value("custom_arrival_type", "");
			return;
		}
		frappe.db.get_doc("Gate Entry", frm.doc.custom_gate_entry).then((gate) => {
			if (gate.arrival_type) {
				frm.set_value("custom_arrival_type", gate.arrival_type);
			}
			if (gate.supplier && !frm.doc.supplier) {
				frm.set_value("supplier", gate.supplier);
			}
			if (gate.po_number && !frm.doc.custom_typed_po_number) {
				frm.set_value("custom_typed_po_number", gate.po_number);
			}
			if (gate.notes && !frm.doc.custom_grn_note) {
				frm.set_value("custom_grn_note", gate.notes);
			}
			_apply_arrival_rules(frm);
		});
	},
	custom_arrival_type(frm) {
		_apply_arrival_rules(frm);
	},
	custom_supplier_bill_is_final(frm) {
		frm.set_value("custom_final_bill_pending", frm.doc.custom_supplier_bill_is_final ? 0 : 1);
		_apply_arrival_rules(frm);
	},
	custom_invoice_number(frm) {
		if (frm.doc.custom_invoice_number && !frm.doc.supplier_delivery_note) {
			frm.set_value("supplier_delivery_note", frm.doc.custom_invoice_number);
		}
	},
});

frappe.ui.form.on("Purchase Receipt Item", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) {
			return;
		}
		frappe.db
			.get_value("Item", row.item_code, ["custom_qc_required", "custom_mfg_date_required", "custom_expiry_required"])
			.then((r) => {
				if (!r.message) {
					return;
				}
				frappe.model.set_value(cdt, cdn, "custom_qc_required", r.message.custom_qc_required ? 1 : 0);
				if (r.message.custom_qc_required) {
					frappe.show_alert({
						message: __("QC required for {0}. Lot will stay pending_qc until passed.", [row.item_code]),
						indicator: "orange",
					});
				}
			});
	},
	qty(frm, cdt, cdn) {
		_recalc_line(cdt, cdn);
	},
	custom_damaged_qty(frm, cdt, cdn) {
		_recalc_line(cdt, cdn);
	},
	custom_ordered_qty(frm, cdt, cdn) {
		_recalc_line(cdt, cdn);
	},
	custom_gst_rate(frm, cdt, cdn) {
		_recalc_line(cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!flt(row.price_list_rate) && flt(row.rate)) {
			frappe.model.set_value(cdt, cdn, "price_list_rate", row.rate);
		}
		_recalc_line(cdt, cdn);
	},
	custom_discount_basis(frm, cdt, cdn) {
		_sync_discount(cdt, cdn);
	},
	discount_percentage(frm, cdt, cdn) {
		_sync_discount(cdt, cdn);
	},
	discount_amount(frm, cdt, cdn) {
		_sync_discount(cdt, cdn);
	},
});

function _apply_arrival_rules(frm) {
	const local = frm.doc.custom_arrival_type === "LOCAL";
	const bill_later = local && !frm.doc.custom_supplier_bill_is_final;
	frm.toggle_reqd("custom_invoice_number", !bill_later);
	frm.toggle_reqd("custom_invoice_date", !bill_later);
	frm.set_df_property("custom_linked_pr_number", "reqd", local ? 1 : 0);
	frm.set_df_property(
		"custom_po_bypass",
		"description",
		__("Store Manager exception only. Local buy must use a Material Request / Local PR, not bypass.")
	);
}

function _has_qty_claim(frm) {
	return (frm.doc.items || []).some(
		(row) => !row.custom_is_reject_line && (flt(row.custom_short_qty) > 0 || flt(row.custom_damaged_qty) > 0)
	);
}

function _recalc_line(cdt, cdn) {
	const row = locals[cdt][cdn];
	if (!row || row.custom_is_reject_line) {
		return;
	}
	const billed = flt(row.custom_ordered_qty);
	const accepted = flt(row.qty);
	const rejected = flt(row.custom_damaged_qty);
	_set_if_diff(cdt, cdn, "custom_short_qty", billed ? Math.max(billed - accepted - rejected, 0) : 0);
	_set_if_diff(cdt, cdn, "custom_excess_qty", billed ? Math.max(accepted + rejected - billed, 0) : 0);
	const base = flt(row.custom_po_qty) || billed;
	_set_if_diff(cdt, cdn, "custom_fill_rate", base ? (accepted / base) * 100 : 0);
	const net = flt(row.amount) || accepted * flt(row.rate);
	_set_if_diff(cdt, cdn, "custom_gst_amount", (net * flt(row.custom_gst_rate)) / 100);
}

function _set_if_diff(cdt, cdn, field, value) {
	const row = locals[cdt][cdn];
	if (Math.abs(flt(row[field]) - flt(value)) > 0.0001) {
		frappe.model.set_value(cdt, cdn, field, value);
	}
}

function _sync_discount(cdt, cdn) {
	const row = locals[cdt][cdn];
	const base = flt(row.price_list_rate);
	if (!base) {
		return;
	}
	if ((row.custom_discount_basis || "Percent") === "Amount") {
		_set_if_diff(cdt, cdn, "discount_percentage", (flt(row.discount_amount) / base) * 100);
	} else {
		_set_if_diff(cdt, cdn, "discount_amount", (base * flt(row.discount_percentage)) / 100);
	}
}

function _pull_gate_entry(frm) {
	if (!frm.doc.custom_gate_entry) {
		frappe.msgprint(__("Link a Gate Entry first."));
		return;
	}
	frappe.call({
		method: "k95_store.inbound.grn_bridge.gate_entry_for_receipt",
		args: { gate_entry: frm.doc.custom_gate_entry },
		freeze: true,
		callback(r) {
			if (!r.message) {
				return;
			}
			_apply_gate_payload(frm, r.message);
		},
	});
}

async function _apply_gate_payload(frm, data) {
	if (data.supplier && !frm.doc.supplier) {
		await frm.set_value("supplier", data.supplier);
	}
	if (data.arrival_type && !frm.doc.custom_arrival_type) {
		await frm.set_value("custom_arrival_type", data.arrival_type);
	}
	if (data.po_number && !frm.doc.custom_typed_po_number) {
		await frm.set_value("custom_typed_po_number", data.po_number);
	}
	if (data.notes && !frm.doc.custom_grn_note) {
		await frm.set_value("custom_grn_note", data.notes);
	}
	_add_invoice_images(frm, data.images || [], "Gate Entry");
	if (!(data.items || []).length) {
		frappe.msgprint(
			__(
				"This gate entry has no Purchase Order items to copy. Upload the invoice and use Read Invoice, or add the lines yourself."
			)
		);
		return;
	}
	for (const item of data.items) {
		await _append_item(frm, item);
	}
	frm.dirty();
}

function _copy_invoice_images(frm) {
	if (!frm.doc.custom_gate_entry) {
		frappe.msgprint(__("Link a Gate Entry first."));
		return;
	}
	frappe.call({
		method: "k95_store.inbound.grn_bridge.gate_entry_for_receipt",
		args: { gate_entry: frm.doc.custom_gate_entry },
		callback(r) {
			const images = (r.message && r.message.images) || [];
			if (!images.length) {
				frappe.msgprint(__("This gate entry has no invoice image."));
				return;
			}
			_add_invoice_images(frm, images, "Gate Entry");
			frm.dirty();
		},
	});
}

function _add_invoice_images(frm, urls, source) {
	const existing = new Set((frm.doc.custom_invoice_images || []).map((row) => row.image));
	(urls || []).forEach((url) => {
		if (!url || existing.has(url)) {
			return;
		}
		const row = frm.add_child("custom_invoice_images");
		row.image = url;
		row.source = source;
		existing.add(url);
	});
	frm.refresh_field("custom_invoice_images");
}

async function _append_item(frm, item) {
	const row = frm.add_child("items");
	await frappe.model.set_value(row.doctype, row.name, "item_code", item.item_code);
	await frappe.model.set_value(row.doctype, row.name, "qty", item.qty);
	if (item.rate) {
		await frappe.model.set_value(row.doctype, row.name, "rate", item.rate);
	}
	await frappe.model.set_value(row.doctype, row.name, "custom_ordered_qty", item.custom_ordered_qty || item.qty);
	if (item.uom) {
		await frappe.model.set_value(row.doctype, row.name, "uom", item.uom);
	}
	if (item.purchase_order) {
		await frappe.model.set_value(row.doctype, row.name, "purchase_order", item.purchase_order);
	}
	if (item.purchase_order_item) {
		await frappe.model.set_value(row.doctype, row.name, "purchase_order_item", item.purchase_order_item);
	}
	if (item.gst_percent) {
		await frappe.model.set_value(row.doctype, row.name, "custom_gst_rate", item.gst_percent);
	}
	if (item.discount_amount) {
		await frappe.model.set_value(row.doctype, row.name, "custom_discount_basis", "Amount");
		await frappe.model.set_value(row.doctype, row.name, "discount_amount", item.discount_amount);
	} else if (item.discount_percent) {
		await frappe.model.set_value(row.doctype, row.name, "custom_discount_basis", "Percent");
		await frappe.model.set_value(row.doctype, row.name, "discount_percentage", item.discount_percent);
	}
	if (item.warehouse) {
		await frappe.model.set_value(row.doctype, row.name, "warehouse", item.warehouse);
	}
}

function _read_invoice(frm) {
	const urls = (frm.doc.custom_invoice_images || []).map((row) => row.image).filter(Boolean);
	frappe.call({
		method: "k95_store.inbound.invoice_ai.read_invoice",
		args: {
			gate_entry: frm.doc.custom_gate_entry,
			file_urls: urls,
		},
		freeze: true,
		freeze_message: __("Reading the invoice"),
		callback(r) {
			if (r.message) {
				_apply_reading(frm, r.message);
			}
		},
	});
}

async function _apply_reading(frm, data) {
	if (data.supplier && !frm.doc.supplier) {
		await frm.set_value("supplier", data.supplier);
	}
	if (data.invoice_number) {
		await frm.set_value("custom_invoice_number", data.invoice_number);
	}
	if (data.invoice_date) {
		await frm.set_value("custom_invoice_date", data.invoice_date);
	}
	if (data.invoice_total) {
		await frm.set_value("custom_bill_grand_total", data.invoice_total);
	}
	if (data.po_number) {
		await frm.set_value("custom_typed_po_number", data.po_number);
	}
	for (const item of data.items || []) {
		await _append_item(frm, item);
	}
	if ((data.unmatched || []).length) {
		const line = __("Invoice lines not matched to an item: {0}", [data.unmatched.join(", ")]);
		const note = [frm.doc.custom_grn_note, line].filter(Boolean).join("\n");
		await frm.set_value("custom_grn_note", note);
		frappe.msgprint({ title: __("Some lines were not matched"), message: line, indicator: "orange" });
	} else if (!(data.items || []).length) {
		frappe.msgprint(__("The invoice was read, but no item lines were found."));
	} else {
		frappe.show_alert({ message: __("Invoice details were written onto this GRN."), indicator: "green" });
	}
	frm.dirty();
}

function _create_debit_note(frm) {
	frappe.call({
		method: "k95_store.inbound.grn_bridge.make_debit_note",
		args: { purchase_receipt: frm.doc.name },
		freeze: true,
		callback(r) {
			if (r.message && r.message.name) {
				frappe.set_route("Form", "Store Debit Note", r.message.name);
			}
		},
	});
}

function _bind_invoice_upload(frm) {
	const field = frm.get_field("custom_invoice_images");
	if (!field || !field.grid || field.grid._k95_invoice_upload) {
		return;
	}
	field.grid._k95_invoice_upload = true;
	field.grid.add_custom_button(__("Upload Invoice Images"), () => {
		const input = document.createElement("input");
		input.type = "file";
		input.accept = "image/*";
		input.multiple = true;
		input.onchange = async () => {
			const files = Array.from(input.files || []);
			if (!files.length) {
				return;
			}
			frappe.dom.freeze(__("Uploading invoice images"));
			try {
				for (const file of files) {
					const file_url = await _upload_file(file);
					_add_invoice_images(frm, [file_url], "GRN");
				}
				frm.dirty();
			} catch (error) {
				frappe.msgprint(__("Could not upload one of the invoice images."));
				console.error(error);
			} finally {
				frappe.dom.unfreeze();
			}
		};
		input.click();
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
