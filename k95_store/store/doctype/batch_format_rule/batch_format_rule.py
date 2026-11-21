import json
from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, nowdate


class BatchFormatRule(Document):
	pass


@frappe.whitelist()
def preview(rule, mfg_date=None, label_date=None):
	doc = frappe.get_doc("Batch Format Rule", rule)
	date = getdate(mfg_date or label_date or nowdate())
	if doc.batch_date_source == "LABEL_START" and label_date:
		date = getdate(label_date)
	parts = []
	try:
		spec = json.loads(doc.format_json or "{}")
	except json.JSONDecodeError:
		spec = {}
	for part in spec.get("parts") or [{"type": "date", "fmt": "%y%m"}]:
		kind = part.get("type")
		if kind == "text":
			parts.append(str(part.get("value") or ""))
		elif kind == "date":
			parts.append(datetime.strftime(date, part.get("fmt") or "%y%m"))
		elif kind == "seq":
			parts.append("0001")
	return "".join(parts) or f"AUTO-{date.strftime('%Y%m%d')}-0001"
