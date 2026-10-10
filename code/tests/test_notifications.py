import json
import os
from unittest.mock import Mock

import pytest

import common
import notifications as note
import store


def confirmed_subscriber(user="alice"):
    """Moto defaults PendingConfirmation to false; no real email is confirmed."""
    sns = common.aws("sns")
    arn = sns.subscribe(TopicArn=os.environ["TOPIC_ARN"], Protocol="email", Endpoint=f"{user}@example.com", ReturnSubscriptionArn=True, Attributes={"FilterPolicy": json.dumps({"userId": [user]}), "FilterPolicyScope": "MessageAttributes"})["SubscriptionArn"]
    p = store.profile(user)
    p.update(email=f"{user}@example.com", subscriptionArn=arn, subscriptionCreatedAt=note.epoch() - 1000, weeklySummary=True)
    store.save_profile(p)
    return sns, arn


def spy_sns(monkeypatch, sns):
    original = common.aws
    client = Mock(wraps=sns)
    monkeypatch.setattr(common, "aws", lambda name: client if name == "sns" else original(name))
    return client


def test_budget_alert_once_and_only_over_threshold(api, expense_data, monkeypatch):
    sns, _ = confirmed_subscriber()
    spy = spy_sns(monkeypatch, sns)
    api("PUT /budget", {"monthlyLimit": 40})
    eid = api("POST /expenses", expense_data)[1]["expenseId"]
    assert spy.publish.call_count == 0
    api("PUT /expenses/{id}", {"total": 41}, eid=eid)
    note.check_budget("alice", "2026-10")
    api("PUT /expenses/{id}", {"total": 42}, eid=eid)
    assert spy.publish.call_count == 1
    assert spy.publish.call_args.kwargs["MessageAttributes"]["userId"]["StringValue"] == "alice"
    assert store.profile("alice")["months"]["2026-10"]["alertState"] == "SENT"


def test_lowering_budget_checks_existing_expenses(api, expense_data, monkeypatch):
    sns, _ = confirmed_subscriber()
    spy = spy_sns(monkeypatch, sns)
    api("POST /expenses", expense_data)
    api("PUT /budget", {"monthlyLimit": 20})
    assert spy.publish.call_count == 1


def test_sns_failure_preserves_expense_and_does_not_blindly_retry(api, expense_data, monkeypatch):
    sns, _ = confirmed_subscriber()
    spy = spy_sns(monkeypatch, sns)
    spy.publish.side_effect = RuntimeError("uncertain delivery")
    api("PUT /budget", {"monthlyLimit": 20})
    status, item = api("POST /expenses", expense_data)
    assert status == 201 and store.get("alice", item["expenseId"])["total"] == 40
    assert store.profile("alice")["months"]["2026-10"]["alertState"] == "UNKNOWN"
    note.check_budget("alice", "2026-10")
    assert spy.publish.call_count == 1


@pytest.mark.parametrize("defect", ["unfiltered", "wrong_user", "pending", "wrong_scope", "unknown_owner", "disabled", "propagating", "missing", "audit_error"])
def test_fail_closed_for_any_unsafe_subscriber(monkeypatch, defect):
    sns, arn = confirmed_subscriber()
    _, bob_arn = confirmed_subscriber("bob")
    if defect == "unfiltered":
        sns.set_subscription_attributes(SubscriptionArn=bob_arn, AttributeName="FilterPolicy", AttributeValue="{}")
    elif defect == "wrong_user":
        sns.set_subscription_attributes(SubscriptionArn=bob_arn, AttributeName="FilterPolicy", AttributeValue=json.dumps({"userId": ["alice"]}))
    elif defect == "wrong_scope":
        sns.set_subscription_attributes(SubscriptionArn=bob_arn, AttributeName="FilterPolicyScope", AttributeValue="MessageBody")
    elif defect == "unknown_owner":
        store.tables()[1].delete_item(Key={"userId": "bob"})
    elif defect == "disabled":
        monkeypatch.setenv("PRIVATE_EMAIL_ENABLED", "false")
    elif defect == "propagating":
        store.tables()[1].put_item(Item={"userId": note.CONTROL, "blockedUntil": note.epoch() + 900})
    elif defect == "missing":
        sns.unsubscribe(SubscriptionArn=arn)
    spy = spy_sns(monkeypatch, sns)
    if defect == "pending":
        def pending(**kwargs):
            result = sns.get_subscription_attributes(**kwargs)
            if kwargs["SubscriptionArn"] == bob_arn:
                result["Attributes"]["PendingConfirmation"] = "true"
            return result
        spy.get_subscription_attributes.side_effect = pending
    if defect == "audit_error":
        spy.get_subscription_attributes.side_effect = RuntimeError("unavailable")
    assert note.send_once("alice", "test", "Subject", "private finances") == "BLOCKED"
    spy.publish.assert_not_called()


def test_subscribe_enforces_verified_identity_and_freezes(api):
    assert api("PUT /budget", {"monthlyLimit": 100, "email": "alice@example.com", "weeklySummary": True})[0] == 200
    p = store.profile("alice")
    assert p["subscriptionArn"]
    assert store.profile(note.CONTROL)["blockedUntil"] == note.epoch() + 900
    attr = common.aws("sns").get_subscription_attributes(SubscriptionArn=p["subscriptionArn"])["Attributes"]
    assert json.loads(attr["FilterPolicy"]) == {"userId": ["alice"]}
    assert api("PUT /budget", {"monthlyLimit": 1, "email": "alice@example.com"}, claims={"sub": "alice", "email": "alice@example.com", "email_verified": "false"})[0] == 400


def test_lock_prevents_parallel_subscription_or_publish():
    with note.topic_lock():
        with pytest.raises(common.Problem, match="busy"):
            with note.topic_lock():
                pass
        assert note.send_once("alice", "test", "subject", "message") == "BLOCKED"


def test_notification_does_not_claim_when_routing_blocked():
    assert note.send_once("alice", "test", "subject", "message") == "BLOCKED"
    assert "notifications" not in store.profile("alice")
