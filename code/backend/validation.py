import re
from datetime import date
from decimal import Decimal, InvalidOperation

from common import Problem

CATEGORIES = {"Groceries", "Dining", "Transport", "Shopping", "Health", "Other"}


def text(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Problem(f"Invalid {name}")
    return value.strip()


def money(value, name="total", positive=False):
    if isinstance(value, (bool, float)) or not isinstance(value, (str, int, Decimal)):
        raise Problem(f"Invalid {name}")
    try:
        result = Decimal(value)
        if not result.is_finite() or result < 0 or result > 100000000 or (positive and result == 0):
            raise InvalidOperation
        if result != result.quantize(Decimal("0.01")):
            raise InvalidOperation
        return result.quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        raise Problem(f"Invalid {name}: use a non-negative amount with at most two decimal places")


def day(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise Problem("Invalid receiptDate; use YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise Problem("Invalid receiptDate")
    return value


def month(value):
    day(str(value) + "-01")
    return value


def currency(value):
    if value != "AUD":
        raise Problem("Only AUD is supported; currency conversion is not performed")
    return value


def expense(data, partial=False):
    allowed = {"merchant", "receiptDate", "total", "gst", "category", "currency"}
    if not isinstance(data, dict) or not data or set(data) - allowed:
        raise Problem("Unknown or missing expense fields")
    if not partial and not {"merchant", "receiptDate", "total"} <= data.keys():
        raise Problem("merchant, receiptDate and total are required")
    out = dict(data)
    if "merchant" in out:
        out["merchant"] = text(out["merchant"], "merchant")
    if "receiptDate" in out:
        out["receiptDate"] = day(out["receiptDate"])
    for key in ("total", "gst"):
        if key in out:
            out[key] = money(out[key], key)
    if "category" in out and out["category"] not in CATEGORIES:
        raise Problem("Invalid category")
    if "currency" in out:
        currency(out["currency"])
    if not partial:
        out.setdefault("category", "Other")
        out.setdefault("currency", "AUD")
    if "gst" in out and "total" in out and out["gst"] > out["total"]:
        raise Problem("GST cannot exceed total")
    return out
