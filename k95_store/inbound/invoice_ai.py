import base64
import json

import frappe
import requests
from frappe import _
from frappe.utils import flt, getdate
from frappe.utils.password import get_decrypted_password


class _Quota(Exception):
	pass


class _Temporary(Exception):
	pass


class _BadModel(Exception):
	pass


PROMPT = """Read the supplier invoice. Return only JSON with this shape:
{
  "supplier_name": "",
  "invoice_number": "",
  "invoice_date": "YYYY-MM-DD",
  "po_number": "",
  "invoice_total": 0,
  "items": [
    {"item_name": "", "qty": 0, "rate": 0, "gst_percent": 0, "discount_percent": 0, "discount_amount": 0}
  ]
}
Rate is the unit price before GST. Use 0 when a number is not printed. Do not invent lines."""


@frappe.whitelist()
def read_invoice(gate_entry=None, file_urls=None):
	if not (
		frappe.has_permission("Purchase Receipt", "create")
		or frappe.has_permission("Purchase Receipt", "write")
	):
		frappe.throw(_("Not permitted to update a GRN."), frappe.PermissionError)
	urls = _urls(gate_entry, file_urls)
	if not urls:
		frappe.throw(
			_("Add an invoice image on the gate entry or on this GRN first."),
			title=_("No invoice image"),
		)
	parsed = _generate(urls[:6])
	return _match(parsed)


def _urls(gate_entry, file_urls):
	urls = []
	if isinstance(file_urls, str) and file_urls:
		try:
			file_urls = json.loads(file_urls)
		except json.JSONDecodeError:
			file_urls = [file_urls]
	for url in file_urls or []:
		if url and url not in urls:
			urls.append(url)
	if gate_entry:
		frappe.has_permission("Gate Entry", "read", doc=gate_entry, throw=True)
		for row in frappe.get_all(
			"Gate Entry Photo",
			filters={"parent": gate_entry, "parentfield": "invoice_photo"},
			fields=["image"],
			order_by="idx asc",
		):
			if row.image and row.image not in urls:
				urls.append(row.image)
	return urls


def _generate(urls):
	keys = frappe.get_all(
		"AI Model Key",
		filters={"enabled": 1},
		fields=["name", "provider", "model", "priority"],
		order_by="priority asc, modified asc",
	)
	if not keys:
		frappe.throw(
			_("Add an enabled AI Model Key before reading an invoice."),
			title=_("No AI model"),
		)
	saw_quota = False
	saw_other = False
	last_reason = _("The model did not return a reading.")
	for row in keys:
		if (row.provider or "Gemini") != "Gemini":
			saw_other = True
			last_reason = _("Only Gemini models can read an invoice right now.")
			_remember(row.name, "skipped", last_reason)
			continue
		secret = get_decrypted_password("AI Model Key", row.name, "api_key", raise_exception=False)
		if not secret:
			saw_other = True
			last_reason = _("This model has no API key.")
			_remember(row.name, "failed", last_reason)
			continue
		model = (row.model or "gemini-2.0-flash").strip()
		for attempt in range(2):
			try:
				text = _call_gemini(model, secret, urls)
				parsed = _parse_json(text)
				_remember(row.name, "ok", "")
				return parsed
			except _Quota as exc:
				saw_quota = True
				last_reason = str(exc)
				_remember(row.name, "limit", last_reason)
				break
			except _Temporary as exc:
				last_reason = str(exc)
				if attempt == 0:
					continue
				saw_other = True
				_remember(row.name, "retry", last_reason)
			except _BadModel as exc:
				saw_other = True
				last_reason = str(exc)
				_remember(row.name, "failed", last_reason)
				break
	if saw_quota and not saw_other:
		frappe.throw(
			_("Every configured AI model has reached its limit. Fill the GRN by hand, or add another model key and try again."),
			title=_("AI limit reached"),
		)
	if saw_quota:
		frappe.throw(
			_("Some AI models have reached their limit, and the others could not read this invoice. Fill the GRN by hand, or try again later."),
			title=_("Invoice was not read"),
		)
	frappe.throw(
		_("The invoice could not be read. {0}").format(last_reason),
		title=_("Invoice was not read"),
	)


def _call_gemini(model, api_key, urls):
	parts = [{"text": PROMPT}]
	for url in urls:
		content, mime = _file_bytes(url)
		parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(content).decode()}})
	endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
	try:
		response = requests.post(
			endpoint,
			params={"key": api_key},
			json={
				"contents": [{"parts": parts}],
				"generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
			},
			timeout=90,
		)
	except requests.Timeout:
		raise _Temporary(_("The model took too long to answer."))
	except requests.RequestException:
		raise _Temporary(_("The model could not be reached."))
	try:
		body = response.json()
	except ValueError:
		body = {}
	status, message = _error_text(body)
	if response.status_code == 429 or status == "RESOURCE_EXHAUSTED" or _looks_like_quota(message):
		raise _Quota(_("This model has reached its limit."))
	if response.status_code in (500, 502, 503, 504):
		raise _Temporary(_("The model did not respond."))
	if response.status_code in (401, 403):
		raise _BadModel(_("This model key was rejected."))
	if response.status_code >= 400:
		raise _BadModel(message or _("This model could not read the invoice."))
	candidates = body.get("candidates") or []
	parts_out = []
	if candidates:
		parts_out = ((candidates[0].get("content") or {}).get("parts") or [])
	text = "\n".join(part.get("text") or "" for part in parts_out)
	if not text:
		raise _BadModel(_("The model returned an empty reading."))
	return text


def _looks_like_quota(message):
	text = (message or "").lower()
	return "quota" in text or "rate limit" in text or ("exceeded" in text and "limit" in text)


def _error_text(body):
	error = body.get("error") if isinstance(body, dict) else None
	if not isinstance(error, dict):
		return "", ""
	return error.get("status") or "", (error.get("message") or "")[:180]


def _parse_json(text):
	raw = (text or "").strip()
	if raw.startswith("```"):
		raw = raw.split("\n", 1)[-1]
		if raw.endswith("```"):
			raw = raw[:-3]
	start = raw.find("{")
	end = raw.rfind("}")
	if start < 0 or end < start:
		raise _BadModel(_("The model did not return invoice data."))
	try:
		data = json.loads(raw[start : end + 1])
	except json.JSONDecodeError:
		raise _BadModel(_("The model did not return invoice data."))
	if not isinstance(data, dict):
		raise _BadModel(_("The model did not return invoice data."))
	return data


def _match(data):
	supplier_name = (data.get("supplier_name") or "").strip()
	po_number = (data.get("po_number") or "").strip()
	items = []
	unmatched = []
	for row in data.get("items") or []:
		if not isinstance(row, dict):
			continue
		label = (row.get("item_name") or row.get("item_code") or "").strip()
		qty = flt(row.get("qty"))
		if not label or qty <= 0:
			continue
		item_code = _match_item(label)
		if not item_code:
			unmatched.append(label)
			continue
		items.append(
			{
				"item_code": item_code,
				"item_name": frappe.db.get_value("Item", item_code, "item_name") or label,
				"qty": qty,
				"rate": flt(row.get("rate")),
				"gst_percent": flt(row.get("gst_percent")),
				"discount_percent": flt(row.get("discount_percent")),
				"discount_amount": flt(row.get("discount_amount")),
			}
		)
	return {
		"supplier": _match_supplier(supplier_name),
		"supplier_name": supplier_name,
		"invoice_number": (data.get("invoice_number") or "").strip(),
		"invoice_date": _clean_date(data.get("invoice_date")),
		"po_number": po_number,
		"purchase_order": po_number if po_number and frappe.db.exists("Purchase Order", po_number) else None,
		"invoice_total": flt(data.get("invoice_total")),
		"items": items,
		"unmatched": unmatched,
	}


def _match_supplier(name):
	if not name:
		return None
	found = frappe.db.get_value("Supplier", {"supplier_name": name}, "name")
	if found:
		return found
	if frappe.db.exists("Supplier", name):
		return name
	like = _like(name)
	rows = frappe.db.sql(
		"""
		select name from `tabSupplier`
		where ifnull(disabled, 0) = 0 and (supplier_name like %s or name like %s)
		order by length(supplier_name) asc
		limit 1
		""",
		(like, like),
	)
	return rows[0][0] if rows else None


def _match_item(label):
	if frappe.db.exists("Item", label):
		return label
	found = frappe.db.get_value("Item", {"item_name": label, "disabled": 0}, "name")
	if found:
		return found
	like = _like(label)
	rows = frappe.db.sql(
		"""
		select name from `tabItem`
		where ifnull(disabled, 0) = 0 and (item_name like %s or name like %s)
		order by length(item_name) asc
		limit 1
		""",
		(like, like),
	)
	return rows[0][0] if rows else None


def _like(value):
	cleaned = (value or "").replace("\\", "").replace("%", "").replace("_", "")
	return f"%{cleaned[:40]}%"


def _clean_date(value):
	if not value:
		return None
	try:
		return str(getdate(value))
	except Exception:
		return None


def _file_bytes(file_url):
	file_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not file_name:
		raise _BadModel(_("An invoice image could not be opened."))
	content = frappe.get_doc("File", file_name).get_content()
	lower = file_url.lower().split("?")[0]
	if lower.endswith(".png"):
		mime = "image/png"
	elif lower.endswith(".webp"):
		mime = "image/webp"
	elif lower.endswith(".pdf"):
		mime = "application/pdf"
	else:
		mime = "image/jpeg"
	return content, mime


def _remember(name, status, message):
	frappe.db.set_value(
		"AI Model Key",
		name,
		{"last_status": status, "last_error": (message or "")[:240]},
		update_modified=False,
	)
	frappe.db.commit()
