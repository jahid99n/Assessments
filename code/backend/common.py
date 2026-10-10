"""Small shared primitives. AWS clients are created only when a handler runs."""
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import boto3
from botocore.config import Config

SYDNEY = ZoneInfo("Australia/Sydney")
MAX_BYTES = 5 * 1024 * 1024
logger = logging.getLogger("expenses")
logger.setLevel(logging.INFO)


class Problem(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def now():
    return datetime.now(timezone.utc)


def stamp():
    return now().isoformat()


def current_month():
    return now().astimezone(SYDNEY).strftime("%Y-%m")


def log(event, **fields):
    # Never log tokens, emails, receipt contents or presigned URLs.
    logger.info(json.dumps({"event": event, **fields}, default=str))


def error_code(error):
    """Useful diagnostics without including service messages or request contents."""
    return getattr(error, "response", {}).get("Error", {}).get("Code", type(error).__name__)


def aws(name):
    return boto3.client(name, region_name=os.getenv("AWS_DEFAULT_REGION", "ap-southeast-2"), config=Config(signature_version="s3v4" if name == "s3" else "v4", connect_timeout=3, read_timeout=5, retries={"max_attempts": 1}))


def encode(value):
    """Emit exact JSON numeric literals without converting Decimal through float."""
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Non-finite number")
        return str(value)
    if isinstance(value, dict):
        return "{" + ",".join(json.dumps(k) + ":" + encode(v) for k, v in value.items()) + "}"
    if isinstance(value, (list, tuple)):
        return "[" + ",".join(encode(v) for v in value) + "]"
    return json.dumps(value)


def response(status, body):
    headers = {"Content-Type": "application/json", "Cache-Control": "no-store"}
    if os.getenv("ALLOWED_ORIGIN"):
        headers["Access-Control-Allow-Origin"] = os.environ["ALLOWED_ORIGIN"]
    return {"statusCode": status, "headers": headers, "body": encode(body)}
