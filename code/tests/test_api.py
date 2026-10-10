import base64
import json
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

import common
import expense_api
import store


def test_manual_crud_updates_totals(api, expense_data):
    assert api("PUT /budget", {"monthlyLimit": 100})[0] == 200
    status, item = api("POST /expenses", expense_data)
    assert status == 201
    eid = item["expenseId"]
    assert api("GET /expenses/{id}", eid=eid)[1]["total"] == Decimal("40.00")
    assert api("GET /expenses")[1]["items"][0]["expenseId"] == eid
    assert api("GET /stats")[1]["thisMonth"] == {"total": 40, "budget": 100, "remaining": 60, "count": 1, "currency": "AUD"}
    assert api("PUT /expenses/{id}", {"total": Decimal("52.10")}, eid=eid)[0] == 200
    assert api("GET /budget")[1]["spent"] == Decimal("52.10")
    assert api("DELETE /expenses/{id}", eid=eid) == (200, {"deleted": True})
    assert api("GET /stats")[1]["thisMonth"]["total"] == 0
    assert api("GET /expenses/{id}", eid=eid)[0] == 404
    assert api("GET /expenses")[1]["items"] == []
    assert api("DELETE /expenses/{id}", eid=eid)[0] == 200


def test_date_edit_moves_month_total(api, expense_data):
    eid = api("POST /expenses", expense_data)[1]["expenseId"]
    api("PUT /expenses/{id}", {"receiptDate": "2026-09-30"}, eid=eid)
    assert api("GET /budget", query={"month": "2026-10"})[1]["spent"] == 0
    assert api("GET /budget", query={"month": "2026-09"})[1]["spent"] == 40


def test_budget_history_and_zero_budget(api):
    for month, limit in [("2026-09", 100), ("2026-10", 0)]:
        assert api("PUT /budget", {"month": month, "monthlyLimit": limit})[0] == 200
    assert api("GET /budget", query={"month": "2026-09"})[1]["monthlyLimit"] == 100
    assert api("GET /budget")[1]["utilisation"] is None


@pytest.mark.parametrize("route", ["GET /expenses", "GET /stats", "GET /budget", "POST /expenses", "POST /upload-url", "PUT /budget", "GET /expenses/{id}", "PUT /expenses/{id}", "DELETE /expenses/{id}"])
def test_every_route_requires_verified_authorizer_context(api, route):
    assert api(route, {}, claims={})[0] == 401


@pytest.mark.parametrize("method", ["GET", "PUT", "DELETE"])
def test_cross_user_item_access(api, expense_data, method):
    eid = api("POST /expenses", expense_data)[1]["expenseId"]
    assert api(f"{method} /expenses/{{id}}", {"total": 1}, user="bob", eid=eid)[0] == 404
    assert store.get("alice", eid)["total"] == 40


def test_cross_user_listing_and_budget(api, expense_data):
    api("POST /expenses", expense_data)
    api("PUT /budget", {"monthlyLimit": 100})
    assert api("GET /expenses", user="bob")[1]["items"] == []
    assert api("GET /budget", user="bob")[1]["monthlyLimit"] == 0


@pytest.mark.parametrize("changes", [{"total": -1}, {"total": "NaN"}, {"total": "Infinity"}, {"total": "1.001"}, {"total": True}, {"receiptDate": "2026-02-30"}, {"merchant": " "}, {"category": "Invalid"}, {"currency": "USD"}, {"userId": "bob"}, {"gst": 100}])
def test_invalid_expense(api, expense_data, changes):
    assert api("POST /expenses", {**expense_data, **changes})[0] == 400


@pytest.mark.parametrize("route,data", [("POST /expenses", {}), ("PUT /budget", {"monthlyLimit": -1}), ("PUT /budget", {"monthlyLimit": 1, "weeklySummary": "true"}), ("PUT /budget", {"monthlyLimit": 1, "email": "bob@example.com"}), ("POST /upload-url", {"contentType": "image/gif"}), ("POST /upload-url", {"contentType": "image/jpeg", "userId": "bob"})])
def test_invalid_route_requests(api, route, data):
    assert api(route, data)[0] == 400


def test_filters_and_pagination(api, expense_data):
    for i in range(5):
        api("POST /expenses", {**expense_data, "category": "Groceries" if i % 2 else "Dining"})
    cursor = None
    found = []
    while True:
        query = {"limit": "1", "category": "Groceries", "month": "2026-10", "from": "2026-10-01", "to": "2026-10-31"}
        if cursor:
            query["cursor"] = cursor
        status, page = api("GET /expenses", query=query)
        assert status == 200
        found.extend(page["items"])
        cursor = page.get("nextCursor")
        if not cursor:
            break
    assert len(found) == 2


def test_cursor_cannot_change_user(api):
    cursor = base64.urlsafe_b64encode(json.dumps({"userId": "bob", "expenseId": "x"}).encode()).decode()
    assert api("GET /expenses", query={"cursor": cursor})[0] == 400


@pytest.mark.parametrize("route,query", [("GET /expenses", {"limit": "0"}), ("GET /expenses", {"limit": "101"}), ("GET /expenses", {"cursor": "!bad"}), ("GET /expenses", {"userId": "bob"}), ("GET /expenses", {"from": "2026-10-31", "to": "2026-10-01"}), ("GET /stats", {"months": "25"}), ("GET /stats", {"months": "abc"}), ("GET /budget", {"month": "2026-13"})])
def test_bad_query(api, route, query):
    assert api(route, query=query)[0] == 400


@pytest.mark.parametrize("mime,extension", [("image/jpeg", ".jpg"), ("image/png", ".png")])
def test_presigned_post_constraints(api, mime, extension):
    status, result = api("POST /upload-url", {"contentType": mime})
    assert status == 200 and result["expiresIn"] == 300
    fields = result["upload"]["fields"]
    policy = json.loads(base64.b64decode(fields["policy"]))
    conditions = policy["conditions"]
    assert ["content-length-range", 1, 5 * 1024 * 1024] in conditions
    assert {"Content-Type": mime} in conditions
    assert {"x-amz-meta-userid": "alice"} in conditions
    assert {"x-amz-meta-expenseid": result["expenseId"]} in conditions
    assert {"key": fields["key"]} in conditions
    assert fields["key"].startswith("receipts/alice/") and fields["key"].endswith(extension)
    assert store.get("alice", result["expenseId"])["status"] == "PENDING"


def test_pending_cannot_be_manually_completed(api):
    eid = api("POST /upload-url", {"contentType": "image/jpeg"})[1]["expenseId"]
    assert api("PUT /expenses/{id}", {"total": 1}, eid=eid)[0] == 409


def test_decimal_roundtrip(api, expense_data):
    for amount in (Decimal("0.10"), Decimal("0.20")):
        api("POST /expenses", {**expense_data, "total": amount, "gst": 0})
    assert api("GET /stats")[1]["thisMonth"]["total"] == Decimal("0.30")


def test_dynamodb_error_is_sanitised(api, monkeypatch):
    def broken():
        raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "secret internal configuration"}}, "Query")
    monkeypatch.setattr(store, "tables", broken)
    status, result = api("GET /expenses")
    assert status == 500 and "secret" not in result["error"]


def test_stale_expense_write_rejected(api, expense_data):
    eid = api("POST /expenses", expense_data)[1]["expenseId"]
    old = store.get("alice", eid)
    api("PUT /expenses/{id}", {"merchant": "New"}, eid=eid)
    with pytest.raises(common.Problem, match="concurrently"):
        store.replace({**old, "merchant": "Old"}, old["revision"])


def test_malformed_body_and_duplicate_fields():
    for raw in ('{"total":NaN}', '{"total":1,"total":2}', '[]', '{broken'):
        event = {"routeKey": "POST /expenses", "body": raw, "requestContext": {"authorizer": {"jwt": {"claims": {"sub": "alice"}}}}}
        assert expense_api.handler(event, None)["statusCode"] == 400
