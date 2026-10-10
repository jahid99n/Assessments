"""Version-pinned S3 receipt processing with conditional leases and deduplication."""
import hashlib
import os
import re
from urllib.parse import unquote_plus
from uuid import uuid4

from botocore.exceptions import ClientError

import common
import notifications
import store
from common import Problem
from receipt_parser import parse


def finish(item, changes):
    # replace checks the revision: an expired worker cannot overwrite a new claim
    # or an API deletion. No unconditional UpdateItem can resurrect an expense.
    result = {**item, **changes}
    result.pop("leaseUntil", None)
    result.pop("leaseToken", None)
    return store.replace(result, item["revision"])


def process(record):
    if record.get("eventSource") != "aws:s3" or not record.get("eventName", "").startswith("ObjectCreated:"):
        return "IGNORED"
    bucket = record.get("s3", {}).get("bucket", {}).get("name")
    obj = record.get("s3", {}).get("object", {})
    key = unquote_plus(obj.get("key", ""))
    if bucket != os.environ["BUCKET"]:
        common.log("receipt_rejected_bucket")
        return "REJECTED"
    match = re.fullmatch(r"receipts/([A-Za-z0-9_-]{1,128})/([0-9a-f-]{36})\.(jpg|png)", key)
    if not match:
        common.log("receipt_rejected_key")
        return "REJECTED"
    user, eid, _ = match.groups()
    try:
        item = store.get(user, eid, internal=True)
    except Problem:
        common.log("receipt_missing_mapping", expenseId=eid)
        return "REJECTED"
    if item.get("kind") != "EXPENSE" or item.get("source") != "receipt" or item.get("imageKey") != key:
        return "REJECTED"
    version = obj.get("versionId")
    if item["status"] == "DELETED":
        if version:
            common.aws("s3").delete_object(Bucket=bucket, Key=key, VersionId=version)
        return "DELETED"
    if item.get("objectVersion") and item["objectVersion"] != version:
        # Presigned POST is reusable until expiry; pin first claimed immutable
        # version so later overwrites can never change the charged receipt.
        if version:
            common.aws("s3").delete_object(Bucket=bucket, Key=key, VersionId=version)
        return "IGNORED_VERSION"
    if item["status"] == "PROCESSED":
        notifications.check_budget(user, item["receiptDate"][:7])
        return "ALREADY_PROCESSED"
    if item["status"] == "FAILED" and not item.get("retryable", False):
        return "FAILED"
    epoch = int(common.now().timestamp())
    if item["status"] == "PROCESSING" and item.get("leaseUntil", 0) >= epoch:
        # Raise to retain Lambda's retry, rather than acknowledging a crashed owner.
        raise RuntimeError("Receipt is being processed; retry later")
    claimed = {**item, "status": "PROCESSING", "leaseToken": str(uuid4()), "leaseUntil": epoch + 90}
    if version:
        claimed["objectVersion"] = version
    item = store.replace(claimed, item["revision"])
    try:
        if not isinstance(version, str) or not version or version == "null":
            raise Problem("Receipt bucket versioning is required")
        s3 = common.aws("s3")
        head = s3.head_object(Bucket=bucket, Key=key, VersionId=version)
        if head.get("Metadata") != {"userid": user, "expenseid": eid}:
            raise Problem("Receipt ownership metadata is invalid")
        if head.get("ContentType") != item["contentType"] or not 1 <= head["ContentLength"] <= common.MAX_BYTES:
            raise Problem("Receipt must be JPEG/PNG and at most 5 MiB")
        stream = s3.get_object(Bucket=bucket, Key=key, VersionId=version)["Body"]
        try:
            image = stream.read(common.MAX_BYTES + 1)
        finally:
            stream.close()
        if len(image) != head["ContentLength"]:
            raise Problem("Invalid receipt size")
        signature_ok = image.startswith(b"\xff\xd8\xff") if item["contentType"] == "image/jpeg" else image.startswith(b"\x89PNG\r\n\x1a\n")
        if not signature_ok:
            raise Problem("Receipt file does not match its image type")
        digest = hashlib.sha256(image).hexdigest()
        marker = {"userId": user, "expenseId": "HASH#" + digest, "kind": "RECEIPT_HASH", "ownerExpenseId": eid}
        try:
            store.tables()[0].put_item(Item=marker, ConditionExpression="attribute_not_exists(expenseId) OR ownerExpenseId = :id", ExpressionAttributeValues={":id": eid})
        except ClientError as error:
            if store.conflict(error):
                raise Problem("Duplicate receipt: this exact image was already submitted")
            raise
        extracted = common.aws("textract").analyze_expense(Document={"S3Object": {"Bucket": bucket, "Name": key, "Version": version}})
        parsed = parse(extracted)
        item.pop("errorMessage", None)
        item = finish(item, {**parsed, "status": "PROCESSED", "retryable": False, "contentHash": digest})
        common.log("receipt_processed", expenseId=eid)
        notifications.check_budget(user, parsed["receiptDate"][:7])
        return "PROCESSED"
    except Problem as error:
        if error.status == 409:
            raise  # lost lease/deletion; never overwrite the winning writer
        finish(item, {"status": "FAILED", "errorMessage": str(error), "retryable": False})
        common.log("receipt_invalid", expenseId=eid)
        return "FAILED"
    except Exception as error:
        permanent = common.error_code(error) in {"UnsupportedDocumentException", "BadDocumentException", "DocumentTooLargeException"}
        if permanent:
            finish(item, {"status": "FAILED", "errorMessage": "Textract could not read this image; upload a clearer JPEG or PNG receipt", "retryable": False})
            common.log("receipt_unreadable", expenseId=eid, code=common.error_code(error))
            return "FAILED"
        # Persist visible failure if DynamoDB is available; still raise so the
        # asynchronous Lambda invocation retries. A failed save leaves a lease
        # that can safely be reclaimed after expiry.
        try:
            finish(item, {"status": "FAILED", "errorMessage": "Processing service unavailable; retry pending", "retryable": True})
        except Exception:
            common.log("receipt_failure_state_unavailable", expenseId=eid)
        common.log("receipt_retry_required", expenseId=eid, code=common.error_code(error))
        raise


def handler(event, context):
    outcomes = []
    errors = False
    for record in event.get("Records", []):
        try:
            outcomes.append(process(record))
        except Exception:
            errors = True
    if errors:
        raise RuntimeError("One or more receipts require retry")
    return {"outcomes": outcomes}
