"""Integration edge cases: pages, notification boundaries, leases and cleanup."""
import json
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

import common
import notifications as note
import receipt_processor as processor
import store
import weekly_summary as weekly
from test_notifications import confirmed_subscriber, spy_sns
from test_receipts import stub_textract


def small_pages(monkeypatch):
    """Force real moto DynamoDB queries/scans to have tiny evaluated pages."""
    original = store.tables
    def tables():
        expenses, budgets = original()
        e = Mock(wraps=expenses)
        b = Mock(wraps=budgets)
        e.query.side_effect = lambda **kwargs: expenses.query(**{**kwargs, "Limit": 1})
        b.scan.side_effect = lambda **kwargs: budgets.scan(**{**kwargs, "Limit": 1})
        return e, b
    monkeypatch.setattr(store, "tables", tables)


def test_totals_and_stats_exhaust_dynamodb_pages(api, expense_data, monkeypatch):
    for amount in (10, 20, 30):
        assert api("POST /expenses", {**expense_data, "total": amount})[0] == 201
    small_pages(monkeypatch)
    assert store.total("alice", "2026-10") == 60
    assert api("GET /stats")[1]["thisMonth"]["total"] == 60
    assert api("GET /budget")[1]["spent"] == 60


def test_weekly_pages_users_and_expenses(api, expense_data, monkeypatch):
    sns, _ = confirmed_subscriber()
    confirmed_subscriber("bob")
    for user in ("alice", "bob"):
        for amount in (10, 20):
            api("POST /expenses", {**expense_data, "total": amount}, user=user)
    spy = spy_sns(monkeypatch, sns)
    small_pages(monkeypatch)
    result = weekly.handler({"scheduledTime": "2026-10-11T22:00:00Z"}, None)
    assert result["sent"] == 2
    assert all("Total: AUD 30.00" in c.kwargs["Message"] for c in spy.publish.call_args_list)
    repeated = weekly.handler({"scheduledTime": "2026-10-11T22:00:00Z"}, None)
    assert repeated["sent"] == 0 and repeated["skipped"] == 2
    assert spy.publish.call_count == 2


def test_receipt_completion_checks_receipt_month_budget(api, receipt, textract_result, monkeypatch):
    sns, _ = confirmed_subscriber()
    api("PUT /budget", {"month": "2024-11", "monthlyLimit": 20})
    spy = spy_sns(monkeypatch, sns)
    eid, event = receipt()
    stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "PROCESSED"
    assert api("GET /budget", query={"month": "2024-11"})[1]["remaining"] == -20
    assert spy.publish.call_count == 1
    assert store.profile("alice")["months"]["2024-11"]["alertState"] == "SENT"


def test_blocked_notification_retries_after_confirmation(api, expense_data, monkeypatch):
    api("PUT /budget", {"monthlyLimit": 20})
    api("POST /expenses", expense_data)
    assert "notifications" not in store.profile("alice")
    sns, _ = confirmed_subscriber()
    spy = spy_sns(monkeypatch, sns)
    assert note.check_budget("alice", "2026-10") == "SENT"
    assert spy.publish.call_count == 1


def test_subscription_replacement_uses_verified_new_email(api):
    sns, old = confirmed_subscriber()
    claims = {"sub": "alice", "email": "new@example.com", "email_verified": "true"}
    status, _ = api("PUT /budget", {"monthlyLimit": 100, "email": "new@example.com"}, claims=claims)
    assert status == 200
    p = store.profile("alice")
    assert p["subscriptionArn"] != old and p["email"] == "new@example.com"
    subs = sns.list_subscriptions_by_topic(TopicArn=p["subscriptionArn"].rsplit(":", 1)[0])["Subscriptions"]
    assert len(subs) == 1 and subs[0]["Endpoint"] == "new@example.com"
    assert store.profile(note.CONTROL)["blockedUntil"] > note.epoch()


def test_resubscribe_after_email_unsubscribe(api):
    sns, arn = confirmed_subscriber()
    sns.unsubscribe(SubscriptionArn=arn)
    status, _ = api("PUT /budget", {"monthlyLimit": 100, "email": "alice@example.com"})
    assert status == 200
    assert store.profile("alice")["subscriptionArn"] != arn


def test_topic_audit_checks_later_subscription_pages(monkeypatch):
    sns, _ = confirmed_subscriber()
    _, bob = confirmed_subscriber("bob")
    topic = bob.rsplit(":", 1)[0]
    sns.set_subscription_attributes(SubscriptionArn=bob, AttributeName="FilterPolicy", AttributeValue="{}")
    subs = sns.list_subscriptions_by_topic(TopicArn=topic)["Subscriptions"]
    spy = spy_sns(monkeypatch, sns)
    paginator = Mock()
    paginator.paginate.return_value = [{"Subscriptions": subs[:1]}, {"Subscriptions": subs[1:]}]
    spy.get_paginator.return_value = paginator
    assert note.send_once("alice", "test", "subject", "private") == "BLOCKED"
    spy.publish.assert_not_called()


def test_unreadable_textract_is_terminal(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    tx.analyze_expense.side_effect = ClientError({"Error": {"Code": "BadDocumentException", "Message": "bad"}}, "AnalyzeExpense")
    assert processor.process(event) == "FAILED"
    assert store.get("alice", eid)["retryable"] is False
    assert processor.process(event) == "FAILED"
    assert tx.analyze_expense.call_count == 1


def test_missing_version_is_visible_failure(receipt):
    eid, event = receipt()
    del event["s3"]["object"]["versionId"]
    assert processor.process(event) == "FAILED"
    assert "versioning" in store.get("alice", eid)["errorMessage"]


def test_expired_worker_cannot_commit_after_reclaim(receipt):
    eid, _ = receipt()
    first = store.get("alice", eid)
    old = store.replace({**first, "status": "PROCESSING", "leaseUntil": 0}, 0)
    fresh = store.replace({**old, "leaseUntil": 100}, old["revision"])
    with pytest.raises(common.Problem):
        processor.finish(old, {"status": "PROCESSED", "total": 100})
    assert store.get("alice", eid)["revision"] == fresh["revision"]


def test_s3_delete_failure_preserves_zero_spending_and_can_retry(api, receipt, textract_result, monkeypatch):
    eid, event = receipt()
    stub_textract(monkeypatch, textract_result)
    processor.process(event)
    original = common.aws
    s3 = Mock(wraps=common.aws("s3"))
    s3.delete_object.side_effect = RuntimeError("temporary failure")
    monkeypatch.setattr(common, "aws", lambda name: s3 if name == "s3" else original(name))
    assert api("DELETE /expenses/{id}", eid=eid)[0] == 500
    assert store.total("alice", "2024-11") == 0
    s3.delete_object.side_effect = None
    assert api("DELETE /expenses/{id}", eid=eid)[0] == 200
    assert common.aws("s3").list_object_versions(Bucket="expense-test-receipts").get("Versions", []) == []


def test_stale_budget_write_is_rejected():
    first = store.save_profile(store.profile("alice"))
    stale = dict(first)
    store.save_profile({**first, "weeklySummary": True})
    with pytest.raises(common.Problem):
        store.save_profile(stale)
    assert store.profile("alice")["weeklySummary"] is True


def test_all_records_attempted_before_batch_retry(receipt, textract_result, monkeypatch):
    _, a = receipt(content=b"\xff\xd8\xffa")
    second, b = receipt(content=b"\xff\xd8\xffb")
    tx = stub_textract(monkeypatch, textract_result)
    tx.analyze_expense.side_effect = [RuntimeError("temporary"), textract_result]
    with pytest.raises(RuntimeError):
        processor.handler({"Records": [a, b]}, None)
    assert store.get("alice", second)["status"] == "PROCESSED"
