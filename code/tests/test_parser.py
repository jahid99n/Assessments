from decimal import Decimal
import pytest
from common import Problem
from categories import classify
from receipt_parser import parse, receipt_date, receipt_money


@pytest.mark.parametrize("raw,expected", [("04/11/2024", "2024-11-04"), ("2024-11-04", "2024-11-04"), ("4 Nov 2024", "2024-11-04"), ("04-11-2024", "2024-11-04"), ("29/02/2024", "2024-02-29")])
def test_australian_dates(raw, expected):
    assert receipt_date(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "11/30/2024", "29/02/2025", "04/11/24", "yesterday"])
def test_invalid_dates_fail(raw):
    with pytest.raises(Problem):
        receipt_date(raw)


@pytest.mark.parametrize("merchant,category", [("Coles", "Groceries"), ("Woolworths", "Groceries"), ("ALDI", "Groceries"), ("Shell", "Transport"), ("BP Highway", "Transport"), ("Uber Eats", "Dining"), ("Unknown", "Other"), ("ABP Supplies", "Other")])
def test_categories(merchant, category):
    assert classify(merchant) == category


def test_coles_fields(textract_result):
    item = parse(textract_result)
    assert item["receiptDate"] == "2024-11-04"
    assert item["total"] == Decimal("40.00") and item["gst"] == Decimal("0.38")
    assert item["category"] == "Groceries" and item["confidence"] == Decimal("97.5")
    assert item["currencySource"] == "application_default"


@pytest.mark.parametrize("field", ["VENDOR_NAME", "INVOICE_RECEIPT_DATE", "TOTAL"])
def test_missing_required_fields(textract_result, field):
    textract_result["ExpenseDocuments"][0]["SummaryFields"] = [f for f in textract_result["ExpenseDocuments"][0]["SummaryFields"] if f["Type"]["Text"] != field]
    with pytest.raises(Problem):
        parse(textract_result)


def test_amount_paid_fallback(textract_result):
    textract_result["ExpenseDocuments"][0]["SummaryFields"][2]["Type"]["Text"] = "AMOUNT_PAID"
    assert parse(textract_result)["total"] == Decimal("40.00")


def test_bare_dollar_inferred_as_usd_is_treated_as_aud(textract_result):
    # Live Textract tags "$12.34" on an Australian receipt as USD.
    textract_result["ExpenseDocuments"][0]["SummaryFields"][2]["Currency"] = {"Code": "USD", "Confidence": 99}
    item = parse(textract_result)
    assert item["currency"] == "AUD" and item["currencySource"] == "assumed_from_dollar_sign"


@pytest.mark.parametrize("code,total,currency_text", [
    ("USD", "$40.00", "USD"), ("USD", "$40.00", "US$"), ("EUR", "$40.00", None), ("GBP", "40.00", None)])
def test_explicit_foreign_currency_rejected(textract_result, code, total, currency_text):
    fields = textract_result["ExpenseDocuments"][0]["SummaryFields"]
    fields[2]["Currency"] = {"Code": code, "Confidence": 99}
    fields[2]["ValueDetection"]["Text"] = total
    if currency_text:
        fields.append({"Type": {"Text": "CURRENCY", "Confidence": 99.0}, "ValueDetection": {"Text": currency_text, "Confidence": 97.5}})
    with pytest.raises(Problem, match="AUD"):
        parse(textract_result)


@pytest.mark.parametrize("raw", ["1,23.00", "-1.00", "NaN", "1.234", "EUR 5.00"])
def test_bad_money(raw):
    with pytest.raises(Problem):
        receipt_money(raw)


def test_grouped_money():
    assert receipt_money("$1,234.50") == Decimal("1234.50")
