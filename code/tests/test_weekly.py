from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

import common
import store
import weekly_summary as weekly
from test_notifications import confirmed_subscriber, spy_sns


@pytest.mark.parametrize("scheduled,start,end", [("2026-10-11T22:00:00Z", "2026-10-05", "2026-10-12"), ("2026-10-04T22:00:00Z", "2026-09-28", "2026-10-05"), ("2026-04-05T23:00:00Z", "2026-03-30", "2026-04-06")])
def test_sydney_weeks_across_dst(scheduled, start, end):
    a, b = weekly.period({"scheduledTime": scheduled})
    assert (a.isoformat(), b.isoformat()) == (start, end)
    assert (b - a).days == 7
    assert datetime.fromisoformat(scheduled.replace("Z", "+00:00")).astimezone(common.SYDNEY).hour == 9


def test_weekly_totals_and_boundaries(api, expense_data):
    for day, total, cat in [("2026-10-04", 999, "Other"), ("2026-10-05", 10, "Groceries"), ("2026-10-11", 20, "Transport"), ("2026-10-12", 999, "Other")]:
        api("POST /expenses", {**expense_data, "receiptDate": day, "total": total, "category": cat})
    api("PUT /budget", {"monthlyLimit": 2000})
    result = weekly.report("alice", date(2026, 10, 5), date(2026, 10, 12))
    assert result["total"] == 30 and result["count"] == 2
    assert result["byCategory"] == {"Groceries": Decimal(10), "Transport": Decimal(20)}
    assert "AUD 1029.00 of AUD 2000.00" in result["message"]
    assert "2026-10-05 to 2026-10-11" in result["message"]


def test_cross_month_budget_comparisons(api, expense_data):
    for month, amount in [("2026-09", 100), ("2026-10", 200)]:
        api("PUT /budget", {"monthlyLimit": amount, "month": month})
    for day in ("2026-09-30", "2026-10-01"):
        api("POST /expenses", {**expense_data, "receiptDate": day})
    result = weekly.report("alice", date(2026, 9, 28), date(2026, 10, 5))
    assert result["total"] == 80
    assert "AUD 40.00 of AUD 100.00" in result["message"]
    assert "AUD 40.00 of AUD 200.00" in result["message"]


def test_user_specific_routing_and_schedule_retry(api, expense_data, monkeypatch):
    sns, _ = confirmed_subscriber()
    confirmed_subscriber("bob")
    spy = spy_sns(monkeypatch, sns)
    api("POST /expenses", expense_data)
    api("POST /expenses", {**expense_data, "total": 70}, user="bob")
    event = {"scheduledTime": "2026-10-11T22:00:00Z"}
    assert weekly.handler(event, None)["sent"] == 2
    weekly.handler(event, None)
    assert spy.publish.call_count == 2
    messages = {c.kwargs["MessageAttributes"]["userId"]["StringValue"]: c.kwargs["Message"] for c in spy.publish.call_args_list}
    assert "Total: AUD 40.00" in messages["alice"] and "Total: AUD 70.00" in messages["bob"]


def test_empty_week():
    data = weekly.report("alice", date(2026, 10, 5), date(2026, 10, 12))
    assert data["total"] == 0 and "No expenses" in data["message"]


@pytest.mark.parametrize("time", ["2026-10-12T09:00:00", "2026-10-13T09:00:00+11:00"])
def test_invalid_schedule_time(time):
    with pytest.raises(ValueError):
        weekly.period({"scheduledTime": time})
