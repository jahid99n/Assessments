"""Parse Textract SummaryFields without inventing missing transaction details."""
import re
from datetime import datetime
from decimal import Decimal

from categories import classify
from common import Problem
import validation


def receipt_date(raw):
    if not isinstance(raw, str):
        raise Problem("Receipt date is missing or invalid")
    # Australian day-first interpretation is intentional for ambiguous dates.
    for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date().isoformat()
        except ValueError:
            pass
    raise Problem("Receipt date is missing or invalid; use a receipt with a four-digit year")


def receipt_money(raw):
    if not isinstance(raw, str):
        raise Problem("Receipt amount is missing or invalid")
    value = re.sub(r"^(?:AUD\s*|A\$\s*|\$\s*)", "", raw.strip(), flags=re.I)
    if not re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", value):
        raise Problem("Receipt amount is missing or invalid")
    return validation.money(value.replace(",", ""))


def parse(result):
    documents = result.get("ExpenseDocuments", [])
    if len(documents) != 1:
        raise Problem("Upload one readable receipt per image")
    fields = {}
    for field in documents[0].get("SummaryFields", []):
        kind = field.get("Type", {}).get("Text")
        old = fields.get(kind)
        if old is None or field.get("ValueDetection", {}).get("Confidence", 0) > old.get("ValueDetection", {}).get("Confidence", 0):
            fields[kind] = field
    def value(kind):
        return fields.get(kind, {}).get("ValueDetection", {}).get("Text")
    merchant = validation.text(value("VENDOR_NAME"), "receipt merchant")
    date = receipt_date(value("INVOICE_RECEIPT_DATE"))
    total_kind = "TOTAL" if value("TOTAL") else "AMOUNT_PAID"
    total = receipt_money(value(total_kind))
    detected_currency = fields.get(total_kind, {}).get("Currency", {}).get("Code") or value("CURRENCY")
    source = "detected" if detected_currency else "application_default"
    # Textract infers USD for a bare "$", which is how Australian receipts print
    # dollars. Only an explicit foreign marker in the receipt text is rejected.
    explicit = " ".join(filter(None, (value(total_kind), value("CURRENCY")))).upper()
    if detected_currency and detected_currency.upper() == "USD" and not re.search(r"USD|US\$", explicit):
        detected_currency, source = "AUD", "assumed_from_dollar_sign"
    currency = validation.currency(detected_currency.upper() if detected_currency else "AUD")
    item = {"merchant": merchant, "receiptDate": date, "total": total, "currency": currency, "currencySource": source, "category": classify(merchant)}
    if value("TAX"):
        item["gst"] = receipt_money(value("TAX"))
        if item["gst"] > total:
            raise Problem("Receipt GST exceeds total")
    confidences = [fields[k].get("ValueDetection", {}).get("Confidence") for k in ("VENDOR_NAME", "INVOICE_RECEIPT_DATE", total_kind)]
    if all(c is not None for c in confidences):
        item["confidence"] = min(Decimal(str(c)) for c in confidences)
    return item
