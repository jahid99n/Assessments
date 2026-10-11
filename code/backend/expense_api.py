"""API Gateway HTTP API payload v2.0; identities come only from verified claims."""
import base64
import binascii
import json
import os
import re
from decimal import Decimal
from uuid import uuid4

from boto3.dynamodb.conditions import Key

import common
import notifications
import store
import validation as valid
from auth import identity
from common import Problem


def body(event):
    raw = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        raw = base64.b64decode(raw, validate=True).decode("utf-8")
    if len(raw) > 16384:
        raise Problem("Request body too large", 413)
    def no_duplicates(pairs):
        out = {}
        for k, v in pairs:
            if k in out:
                raise Problem("Duplicate JSON field")
            out[k] = v
        return out
    data = json.loads(raw, parse_float=Decimal, parse_constant=lambda x: (_ for _ in ()).throw(Problem("Invalid JSON number")), object_pairs_hook=no_duplicates)
    if not isinstance(data, dict):
        raise Problem("JSON object required")
    return data


def new_item(user, source, status):
    return {"userId": user, "expenseId": str(uuid4()), "kind": "EXPENSE", "source": source, "status": status, "createdAt": common.stamp(), "updatedAt": common.stamp(), "revision": 0}


def create(user, data):
    item = {**new_item(user, "manual", "PROCESSED"), **valid.expense(data)}
    store.tables()[0].put_item(Item=item, ConditionExpression="attribute_not_exists(expenseId)")
    notifications.check_budget(user, item["receiptDate"][:7])
    return store.public(item)


def upload(user, data):
    if set(data) != {"contentType"} or data["contentType"] not in ("image/jpeg", "image/png"):
        raise Problem("contentType must be image/jpeg or image/png")
    item = new_item(user, "receipt", "PENDING")
    extension = "jpg" if data["contentType"] == "image/jpeg" else "png"
    item.update(imageKey=f"receipts/{user}/{item['expenseId']}.{extension}", contentType=data["contentType"])
    fields = {"Content-Type": data["contentType"], "x-amz-meta-userid": user, "x-amz-meta-expenseid": item["expenseId"]}
    signed = common.aws("s3").generate_presigned_post(os.environ["BUCKET"], item["imageKey"], Fields=fields, Conditions=[{k: v} for k, v in fields.items()] + [["content-length-range", 1, common.MAX_BYTES]], ExpiresIn=300)
    store.tables()[0].put_item(Item=item, ConditionExpression="attribute_not_exists(expenseId)")
    return {"expenseId": item["expenseId"], "upload": signed, "expiresIn": 300}


def listing(user, query):
    if set(query) - {"month", "category", "from", "to", "limit", "cursor"}:
        raise Problem("Unknown query parameter")
    if "month" in query:
        valid.month(query["month"])
    if "category" in query and query["category"] not in valid.CATEGORIES:
        raise Problem("Invalid category")
    for key in ("from", "to"):
        if key in query:
            valid.day(query[key])
    if query.get("from", "") > query.get("to", "9999"):
        raise Problem("Invalid date range")
    limit = int(query.get("limit", "25"))
    if not 1 <= limit <= 100:
        raise Problem("limit must be 1..100")
    args = {"KeyConditionExpression": Key("userId").eq(user), "Limit": limit, "ConsistentRead": True}
    if query.get("cursor"):
        cursor = json.loads(base64.urlsafe_b64decode(query["cursor"]).decode())
        if not isinstance(cursor, dict) or set(cursor) != {"userId", "expenseId"} or cursor["userId"] != user or not isinstance(cursor["expenseId"], str):
            raise Problem("Invalid cursor")
        args["ExclusiveStartKey"] = cursor
    result = store.tables()[0].query(**args)
    items = []
    for item in result["Items"]:
        day = item.get("receiptDate", "")
        if item.get("kind") != "EXPENSE" or item["status"] == "DELETED":
            continue
        if ("from" in query or "to" in query) and not day:
            continue
        if "month" in query and not day.startswith(query["month"]):
            continue
        if "category" in query and item.get("category") != query["category"]:
            continue
        if "from" in query and day < query["from"] or "to" in query and day > query["to"]:
            continue
        items.append(store.public(item))
    out = {"items": items}
    if "LastEvaluatedKey" in result:
        out["nextCursor"] = base64.urlsafe_b64encode(json.dumps(result["LastEvaluatedKey"]).encode()).decode()
    return out


def detail(user, eid):
    item = store.get(user, eid)
    out = store.public(item)
    if item.get("imageKey"):
        params = {"Bucket": os.environ["BUCKET"], "Key": item["imageKey"]}
        if item.get("objectVersion"):
            params["VersionId"] = item["objectVersion"]
        out["imageUrl"] = common.aws("s3").generate_presigned_url("get_object", Params=params, ExpiresIn=300)
    return out


def edit(user, eid, data):
    changes = valid.expense(data, partial=True)
    item = store.get(user, eid)
    if item["status"] != "PROCESSED":
        raise Problem("Only completed expenses can be edited", 409)
    old_month = item["receiptDate"][:7]
    updated = {**item, **changes}
    if updated.get("gst", 0) > updated["total"]:
        raise Problem("GST cannot exceed total")
    updated = store.replace(updated, item["revision"])
    for period in {old_month, updated["receiptDate"][:7]}:
        notifications.check_budget(user, period)
    return store.public(updated)


def delete(user, eid):
    # Tombstone first: a concurrent processor cannot recreate a deleted expense.
    item = store.get(user, eid, internal=True)
    if item.get("kind") != "EXPENSE":
        raise Problem("Expense not found", 404)
    if item["status"] != "DELETED":
        item = store.replace({**item, "status": "DELETED"}, item["revision"])
    if item.get("imageKey"):
        s3 = common.aws("s3")
        # Purge all versions of this exact key. A replayed upload within the five
        # minute policy window is discarded by the processor's tombstone check.
        for page in s3.get_paginator("list_object_versions").paginate(Bucket=os.environ["BUCKET"], Prefix=item["imageKey"]):
            for version in page.get("Versions", []) + page.get("DeleteMarkers", []):
                if version["Key"] == item["imageKey"]:
                    s3.delete_object(Bucket=os.environ["BUCKET"], Key=item["imageKey"], VersionId=version["VersionId"])
    if item.get("receiptDate"):
        notifications.check_budget(user, item["receiptDate"][:7])
    return {"deleted": True}


def stats(user, query):
    if set(query) - {"months"}:
        raise Problem("Unknown query parameter")
    count = int(query.get("months", "6"))
    if not 1 <= count <= 24:
        raise Problem("months must be 1..24")
    current = common.current_month()
    y, m = map(int, current.split("-"))
    periods = [f"{(y * 12 + m - 1 - i) // 12:04d}-{(y * 12 + m - 1 - i) % 12 + 1:02d}" for i in reversed(range(count))]
    by_month = dict.fromkeys(periods, Decimal("0.00"))
    by_category = {}
    expense_count = 0
    for item in store.rows(user):
        if item["status"] != "PROCESSED" or item.get("currency") != "AUD":
            continue
        period = item["receiptDate"][:7]
        if period in by_month:
            by_month[period] += item["total"]
        if period == current:
            category = item["category"]
            by_category[category] = by_category.get(category, Decimal("0.00")) + item["total"]
            expense_count += 1
    budget = store.profile(user).get("months", {}).get(current, {}).get("monthlyLimit", Decimal("0.00"))
    return {"byCategory": by_category, "byMonth": by_month, "thisMonth": {"total": by_month[current], "budget": budget, "remaining": budget - by_month[current], "count": expense_count, "currency": "AUD"}}


def put_budget(user, claims, data):
    if set(data) - {"monthlyLimit", "month", "currency", "email", "weeklySummary"} or "monthlyLimit" not in data:
        raise Problem("monthlyLimit required; unknown fields are not accepted")
    limit = valid.money(data["monthlyLimit"], "monthlyLimit")
    period = valid.month(data.get("month", common.current_month()))
    valid.currency(data.get("currency", "AUD"))
    if "weeklySummary" in data and not isinstance(data["weeklySummary"], bool):
        raise Problem("weeklySummary must be a boolean")
    email = data.get("email")
    if email is not None:
        valid.text(email, "email", 254)
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            raise Problem("Invalid email")
        notifications.subscribe(user, email, claims)
    p = store.profile(user)
    if data.get("weeklySummary") and not p.get("subscriptionArn"):
        raise Problem("Set your verified email before enabling summaries")
    periods = p.setdefault("months", {})
    if period not in periods and len(periods) >= 120:
        raise Problem("Budget history limit reached", 409)
    periods[period] = {**periods.get(period, {}), "monthlyLimit": limit, "currency": "AUD", "updatedAt": common.stamp()}
    p["weeklySummary"] = data.get("weeklySummary", p.get("weeklySummary", False))
    store.save_profile(p)
    notifications.check_budget(user, period)
    return get_budget(user, {"month": period})


def get_budget(user, query):
    if set(query) - {"month"}:
        raise Problem("Unknown query parameter")
    period = valid.month(query.get("month", common.current_month()))
    out = store.budget_view(user, period)
    out["subscriptionStatus"] = notifications.subscription_status(user)
    return out


def handler(event, context):
    try:
        user, claims = identity(event)
        route = event.get("routeKey", "")
        query = event.get("queryStringParameters") or {}
        eid = (event.get("pathParameters") or {}).get("id", "")
        if "{id}" in route and not re.fullmatch(r"[0-9a-f-]{36}", eid):
            raise Problem("Expense not found", 404)
        if route == "POST /expenses":
            return common.response(201, create(user, body(event)))
        if route == "POST /upload-url":
            out = upload(user, body(event))
        elif route == "GET /expenses":
            out = listing(user, query)
        elif route == "GET /expenses/{id}":
            out = detail(user, eid)
        elif route == "PUT /expenses/{id}":
            out = edit(user, eid, body(event))
        elif route == "DELETE /expenses/{id}":
            out = delete(user, eid)
        elif route == "GET /stats":
            out = stats(user, query)
        elif route == "GET /budget":
            out = get_budget(user, query)
        elif route == "PUT /budget":
            out = put_budget(user, claims, body(event))
        else:
            raise Problem("Route not found", 404)
        return common.response(200, out)
    except Problem as error:
        return common.response(error.status, {"error": str(error)})
    except (ValueError, TypeError, binascii.Error, UnicodeError):
        return common.response(400, {"error": "Invalid request"})
    except Exception:
        common.log("api_failure", requestId=getattr(context, "aws_request_id", None))
        return common.response(500, {"error": "Service temporarily unavailable"})
