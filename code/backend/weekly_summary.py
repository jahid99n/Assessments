"""Monday 09:00 Sydney job, summarising the preceding seven complete local days."""
from datetime import datetime, timedelta
from decimal import Decimal

import common
import notifications
import store


def period(event):
    # Scheduler must pass its scheduled-time context value. Retries retain the
    # original reporting window, even if execution crosses midnight.
    scheduled = event.get("scheduledTime")
    instant = datetime.fromisoformat(scheduled.replace("Z", "+00:00")) if scheduled else common.now()
    if instant.tzinfo is None:
        raise ValueError("scheduledTime must include a timezone")
    end = instant.astimezone(common.SYDNEY).date()
    if end.weekday() != 0:
        raise ValueError("Weekly summary requires a Monday scheduled time")
    return end - timedelta(days=7), end


def report(user, start, end):
    categories = {}
    count = 0
    monthly = {}
    for item in store.rows(user):
        if item["status"] != "PROCESSED" or item.get("currency") != "AUD":
            continue
        date = item["receiptDate"]
        if start.isoformat() <= date < end.isoformat():
            count += 1
            cat = item["category"]
            categories[cat] = categories.get(cat, Decimal("0.00")) + item["total"]
        # Compare each touched month's spend through the report cutoff, excluding
        # future-dated expenses and Monday's new transactions.
        if start.strftime("%Y-%m") <= date[:7] <= (end - timedelta(days=1)).strftime("%Y-%m") and date < end.isoformat():
            monthly[date[:7]] = monthly.get(date[:7], Decimal("0.00")) + item["total"]
    total = sum(categories.values(), Decimal("0.00"))
    lines = [f"Weekly spending: {start.isoformat()} to {(end - timedelta(days=1)).isoformat()} (Australia/Sydney)", f"Total: AUD {total:.2f}; expenses: {count}"]
    lines += [f"{cat}: AUD {amount:.2f}" for cat, amount in sorted(categories.items())]
    if not categories:
        lines.append("No expenses recorded this week.")
    budgets = store.profile(user).get("months", {})
    touched = {start.strftime("%Y-%m"), (end - timedelta(days=1)).strftime("%Y-%m")}
    for month in sorted(touched):
        spent = monthly.get(month, Decimal("0.00"))
        limit = budgets.get(month, {}).get("monthlyLimit")
        if limit is None:
            lines.append(f"{month}: no budget set; spending through cutoff AUD {spent:.2f}.")
        else:
            utilisation = f"{spent / limit * 100:.2f}%" if limit else "not applicable (zero budget)"
            lines.append(f"{month}: AUD {spent:.2f} of AUD {limit:.2f}; used {utilisation}; remaining AUD {limit - spent:.2f}.")
    return {"total": total, "count": count, "byCategory": categories, "message": "\n".join(lines)}


def handler(event, context):
    start, end = period(event)
    results = {"sent": 0, "blocked": 0, "skipped": 0}
    args = {"ConsistentRead": True}
    table = store.tables()[1]
    while True:
        page = table.scan(**args)  # deliberate batch enumeration; never expense Scan
        for p in page["Items"]:
            if p.get("weeklySummary") is not True:
                continue
            user = p["userId"]
            try:
                data = report(user, start, end)
                state = notifications.send_once(user, f"weekly:{start.isoformat()}", "Your weekly spending summary", data["message"])
                result_key = "sent" if state == "SENT" else "skipped" if state == "ALREADY_SENT" else "blocked"
                results[result_key] += 1
            except Exception:
                common.log("weekly_user_failed")
                results["blocked"] += 1
        if "LastEvaluatedKey" not in page:
            break
        args["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    common.log("weekly_summary_finished", **results)
    return {"start": start.isoformat(), "endExclusive": end.isoformat(), **results}
