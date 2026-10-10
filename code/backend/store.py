"""Two-table access. Financial totals always use strongly consistent, paged queries."""
import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from common import Problem, current_month, stamp


def tables():
    db = boto3.resource("dynamodb", region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"))
    return db.Table(os.environ["EXPENSES_TABLE"]), db.Table(os.environ["BUDGETS_TABLE"])


def conflict(error):
    return isinstance(error, ClientError) and error.response["Error"]["Code"] == "ConditionalCheckFailedException"


def get(user, eid, internal=False):
    item = tables()[0].get_item(Key={"userId": user, "expenseId": eid}, ConsistentRead=True).get("Item")
    if not item or (not internal and (item.get("kind") != "EXPENSE" or item["status"] == "DELETED")):
        raise Problem("Expense not found", 404)
    return item


def rows(user):
    table = tables()[0]
    args = {"KeyConditionExpression": Key("userId").eq(user), "ConsistentRead": True}
    while True:
        result = table.query(**args)
        yield from (r for r in result["Items"] if r.get("kind") == "EXPENSE" and r["status"] != "DELETED")
        if "LastEvaluatedKey" not in result:
            break
        args["ExclusiveStartKey"] = result["LastEvaluatedKey"]


def total(user, period):
    return sum((r["total"] for r in rows(user) if r["status"] == "PROCESSED" and r.get("currency") == "AUD" and r["receiptDate"].startswith(period)), Decimal("0.00"))


def profile(user):
    return tables()[1].get_item(Key={"userId": user}, ConsistentRead=True).get("Item", {"userId": user, "months": {}, "weeklySummary": False, "revision": 0})


def save_profile(item):
    revision = item.get("revision", 0)
    item = {**item, "revision": revision + 1, "updatedAt": stamp()}
    try:
        tables()[1].put_item(Item=item, ConditionExpression="attribute_not_exists(userId) OR revision = :v", ExpressionAttributeValues={":v": revision})
    except ClientError as error:
        if conflict(error):
            raise Problem("Settings changed concurrently; please retry", 409)
        raise
    return item


def budget_view(user, period=None):
    period = period or current_month()
    p = profile(user)
    b = p.get("months", {}).get(period, {})
    limit = b.get("monthlyLimit", Decimal("0.00"))
    spent = total(user, period)
    return {"month": period, "monthlyLimit": limit, "currency": "AUD", "email": p.get("email", ""), "weeklySummary": p.get("weeklySummary", False), "subscriptionStatus": p.get("subscriptionStatus", "not_subscribed"), "spent": spent, "remaining": limit - spent, "utilisation": (spent / limit * 100).quantize(Decimal("0.01")) if limit else None, "notificationState": b.get("alertState", "not_sent")}


def replace(item, expected_revision):
    item = {**item, "revision": expected_revision + 1, "updatedAt": stamp()}
    try:
        tables()[0].put_item(Item=item, ConditionExpression="revision = :r AND #s <> :d", ExpressionAttributeNames={"#s": "status"}, ExpressionAttributeValues={":r": expected_revision, ":d": "DELETED"})
    except ClientError as error:
        if conflict(error):
            raise Problem("Expense changed concurrently; please retry", 409)
        raise
    return item


def public(item):
    return {k: v for k, v in item.items() if k not in {"kind", "leaseUntil", "leaseToken", "objectVersion", "contentHash"}}
