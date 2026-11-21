app_name = "k95_store"
app_title = "Store"
app_publisher = "K95 Foods Private Limited"
app_description = "Factory store inventory on native ERPNext stock"
app_email = "erpnextapi@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

app_include_js = [
	"/assets/k95_store/js/gate_entry.js",
	"/assets/k95_store/js/purchase_receipt.js",
	"/assets/k95_store/js/item.js",
	"/assets/k95_store/js/batch.js",
	"/assets/k95_store/js/warehouse.js",
]

after_install = "k95_store.setup.after_install"
before_migrate = "k95_store.setup.before_migrate"
after_migrate = "k95_store.setup.after_migrate"

doc_events = {
	"Quality Inspection": {
		"validate": "k95_store.inbound.qc.link_quality_inspection",
	},
	"Purchase Receipt": {
		"before_validate": "k95_store.inbound.grn.before_validate_purchase_receipt",
		"validate": "k95_store.inbound.grn.validate_purchase_receipt",
		"before_submit": "k95_store.inbound.grn.before_submit_purchase_receipt",
		"on_submit": "k95_store.inbound.grn.on_submit_purchase_receipt",
		"on_cancel": "k95_store.inbound.grn.on_cancel_purchase_receipt",
	},
	"Stock Entry": {
		"validate": "k95_store.stock.utils.validate_stock_entry",
		"on_submit": "k95_store.stock.lots.on_stock_voucher_submit",
		"on_cancel": "k95_store.stock.lots.on_stock_voucher_cancel",
	},
	"Stock Reconciliation": {
		"on_submit": "k95_store.stock.lots.on_stock_voucher_submit",
		"on_cancel": "k95_store.stock.lots.on_stock_voucher_cancel",
	},
	"Batch": {
		"validate": "k95_store.stock.lots.validate_batch",
	},
}

website_route_rules = [
	{"from_route": "/gate-entry", "to_route": "gate-entry"},
]

override_doctype_dashboards = {
	"Purchase Receipt": ["k95_store.inbound.grn_bridge.get_purchase_receipt_dashboard"],
}
