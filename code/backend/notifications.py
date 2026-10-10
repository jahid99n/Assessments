"""Fail-closed SNS routing. All application subscription changes share one lock.

The topic must be dedicated to this application. Phase 3 must restrict external
subscription/filter mutations before PRIVATE_EMAIL_ENABLED is enabled.
"""
import json
import os
from contextlib import contextmanager
from uuid import uuid4

from botocore.exceptions import ClientError

import common
import store
from common import Problem, log

CONTROL = "!SNS_CONTROL"


def epoch():
    return int(common.now().timestamp())


@contextmanager
def topic_lock():
    table = store.tables()[1]
    token = str(uuid4())
    try:
        table.update_item(Key={"userId": CONTROL}, UpdateExpression="SET lockToken = :t, lockUntil = :e", ConditionExpression="attribute_not_exists(lockUntil) OR lockUntil < :n", ExpressionAttributeValues={":t": token, ":e": epoch() + 120, ":n": epoch()})
    except ClientError as error:
        if store.conflict(error):
            raise Problem("Notifications temporarily busy", 503)
        raise
    try:
        yield token
    finally:
        try:
            table.update_item(Key={"userId": CONTROL}, UpdateExpression="REMOVE lockToken, lockUntil", ConditionExpression="lockToken = :t", ExpressionAttributeValues={":t": token})
        except ClientError:
            log("notification_lock_release_failed")


def subscribe(user, email, claims):
    if claims.get("email_verified") not in (True, "true") or email != claims.get("email"):
        raise Problem("Notifications require your verified Cognito email")
    with topic_lock():
        p = store.profile(user)
        sns = common.aws("sns")
        if p.get("email") == email and p.get("subscriptionArn"):
            try:
                attr = sns.get_subscription_attributes(SubscriptionArn=p["subscriptionArn"])["Attributes"]
                if (attr.get("Endpoint") != email or attr.get("TopicArn") != os.environ["TOPIC_ARN"]
                        or attr.get("Protocol") != "email" or json.loads(attr.get("FilterPolicy", "null")) != {"userId": [user]}
                        or attr.get("FilterPolicyScope", "MessageAttributes") != "MessageAttributes"):
                    raise Problem("Existing subscription requires operator review", 503)
                return
            except ClientError as error:
                if error.response["Error"]["Code"] not in {"NotFound", "NotFoundException"}:
                    raise
        # Freeze BEFORE changing SNS. Failure leaves publishing disabled for 15 min;
        # orphaned subscriptions then also fail the complete topic audit.
        store.tables()[1].update_item(Key={"userId": CONTROL}, UpdateExpression="SET blockedUntil = :b", ExpressionAttributeValues={":b": epoch() + 900})
        if p.get("subscriptionArn"):
            sns.unsubscribe(SubscriptionArn=p["subscriptionArn"])
        arn = sns.subscribe(TopicArn=os.environ["TOPIC_ARN"], Protocol="email", Endpoint=email, ReturnSubscriptionArn=True, Attributes={"FilterPolicy": json.dumps({"userId": [user]}), "FilterPolicyScope": "MessageAttributes"})["SubscriptionArn"]
        p.update(email=email, subscriptionArn=arn, subscriptionStatus="pending_confirmation", subscriptionCreatedAt=epoch())
        store.save_profile(p)


def audit(user, token):
    """Verify every subscriber, not merely the intended recipient. Raise to block."""
    if os.getenv("PRIVATE_EMAIL_ENABLED", "false") != "true":
        raise Problem("Private email has not been enabled by the deployment operator", 503)
    control = store.profile(CONTROL)
    if control.get("lockToken") != token or control.get("lockUntil", 0) < epoch() + 20 or control.get("blockedUntil", 0) > epoch():
        raise Problem("Notification isolation is not ready", 503)
    sns = common.aws("sns")
    topic = os.environ["TOPIC_ARN"]
    target = store.profile(user)
    found = False
    for page in sns.get_paginator("list_subscriptions_by_topic").paginate(TopicArn=topic):
        for sub in page["Subscriptions"]:
            arn = sub["SubscriptionArn"]
            if not arn.startswith(topic + ":") or sub.get("Protocol") != "email":
                raise Problem("Unsafe notification subscription", 503)
            attr = sns.get_subscription_attributes(SubscriptionArn=arn)["Attributes"]
            policy = json.loads(attr.get("FilterPolicy", "null"))
            ids = policy.get("userId") if isinstance(policy, dict) else None
            if not isinstance(ids, list) or len(ids) != 1 or not isinstance(ids[0], str) or policy != {"userId": ids}:
                raise Problem("Unsafe notification filter", 503)
            owner = store.profile(ids[0])
            if (attr.get("PendingConfirmation") != "false" or attr.get("FilterPolicyScope", "MessageAttributes") != "MessageAttributes"
                    or attr.get("TopicArn") != topic or attr.get("Protocol") != "email"
                    or owner.get("subscriptionArn") != arn or not owner.get("email")
                    or owner["email"] != sub.get("Endpoint") or owner["email"] != attr.get("Endpoint")
                    or owner.get("subscriptionCreatedAt", epoch()) + 900 > epoch()):
                raise Problem("Notification subscription is not verified", 503)
            found |= ids[0] == user and arn == target.get("subscriptionArn")
    if not found:
        raise Problem("Confirmed notification subscription not found", 503)
    # Re-check the lease after a potentially multi-page audit.
    control = store.profile(CONTROL)
    if control.get("lockToken") != token or control.get("lockUntil", 0) < epoch() + 20:
        raise Problem("Notification verification expired", 503)
    return sns


def subscription_status(user):
    if not store.profile(user).get("subscriptionArn"):
        return "not_subscribed"
    try:
        with topic_lock() as token:
            audit(user, token)
        return "confirmed"
    except Exception:
        return "pending_or_blocked"


def send_once(user, key, subject, message, month=None):
    """Claim before publishing. Uncertain delivery is NOT automatically re-sent.

    A crash after SNS accepts a message cannot be atomically committed to DynamoDB.
    Keep CLAIMED/UNKNOWN for operator review to favour avoiding duplicate emails.
    """
    try:
        with topic_lock() as token:
            sns = audit(user, token)
            p = store.profile(user)
            history = p.setdefault("notifications", {})
            if key in history:
                return "ALREADY_" + history[key]
            history[key] = "CLAIMED"
            if month:
                p["months"][month]["alertState"] = "CLAIMED"
            p = store.save_profile(p)
            try:
                sns.publish(TopicArn=os.environ["TOPIC_ARN"], Subject=subject, Message=message, MessageAttributes={"userId": {"DataType": "String", "StringValue": user}})
                state = "SENT"
            except Exception as error:
                state = "UNKNOWN"
                log("notification_delivery_unknown", notificationKey=key, code=common.error_code(error))
            p["notifications"][key] = state
            if month:
                p["months"][month]["alertState"] = state
                if state == "SENT":
                    p["lastAlertMonth"] = month
            store.save_profile(p)
            return state
    except Exception as error:
        log("notification_blocked_or_failed", notificationKey=key, code=common.error_code(error))
        return "BLOCKED"


def check_budget(user, period):
    try:
        b = store.budget_view(user, period)
        if period not in store.profile(user).get("months", {}) or b["spent"] <= b["monthlyLimit"]:
            return "NOT_REQUIRED"
        return send_once(user, f"budget:{period}", "Monthly budget exceeded", f"Your {period} spending is AUD {b['spent']:.2f}.\nBudget: AUD {b['monthlyLimit']:.2f}.\nOver budget: AUD {-b['remaining']:.2f}.", period)
    except Exception:
        log("budget_check_failed")
        return "BLOCKED"
