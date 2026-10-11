"""Loopback-only test gateway/S3 transport. NEVER package/deploy this harness.

Application handlers are real. Cognito/Gateway identity is a fixed test mapping;
moto simulates S3/DynamoDB/SNS, and only Textract responses are fabricated.
"""
import base64
import json
import os
import sys
import threading
from datetime import datetime, timezone
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
import boto3
import botocore.httpsession
from botocore.exceptions import ClientError
from moto import mock_aws
import common
import expense_api
import receipt_processor

LOCK = threading.RLock()
POLICIES = {}
EVENTS = {}
SCENARIO = {"mode": "success"}
ORIGIN = "http://127.0.0.1:5180"
BUCKET = "integration-receipts"
REAL_AWS = common.aws


class Textract:
    def analyze_expense(self, **kwargs):
        if SCENARIO["mode"] == "transient":
            SCENARIO["mode"] = "success"
            raise ClientError({"Error": {"Code": "ThrottlingException", "Message": "local fixture"}}, "AnalyzeExpense")
        date = SCENARIO.get("date", common.now().astimezone(common.SYDNEY).strftime("%d/%m/%Y"))
        fields = {"VENDOR_NAME": "Coles Integration", "INVOICE_RECEIPT_DATE": date, "TOTAL": "$40.00", "TAX": "$0.38"}
        if SCENARIO["mode"] == "missing_total":
            del fields["TOTAL"]
        return {"ExpenseDocuments": [{"SummaryFields": [
            {"Type": {"Text": key}, "ValueDetection": {"Text": value, "Confidence": 99.0}}
            for key, value in fields.items()
        ]}]}


def process(eid):
    with LOCK:
        try:
            return receipt_processor.handler({"Records": [EVENTS[eid]]}, None)
        except RuntimeError:
            return {"retryRequired": True}


def check_post(fields, content):
    """Enforce the actual generated policy in our simulation, not moto's lax POST."""
    issued = POLICIES.get(fields.get("policy"))
    if not issued or fields != issued:
        raise ValueError("Signed fields were changed")
    policy = json.loads(base64.b64decode(fields["policy"]))
    if datetime.fromisoformat(policy["expiration"].replace("Z", "+00:00")) <= datetime.now(timezone.utc):
        raise ValueError("Expired policy")
    for condition in policy["conditions"]:
        if isinstance(condition, dict):
            for key, value in condition.items():
                if (BUCKET if key == "bucket" else fields.get(key)) != value:
                    raise ValueError("Policy condition failed")
        elif condition[0] == "content-length-range":
            if not condition[1] <= len(content) <= condition[2]:
                raise ValueError("Size policy failed")
        else:
            raise ValueError("Unsupported local policy condition")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # no tokens, multipart fields or financial data in access logs

    def reply(self, status, body=None):
        data = common.encode(body).encode() if body is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", ORIGIN)
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass  # React legitimately cancels stale reads when changing pages.

    def do_OPTIONS(self):
        self.reply(204)

    def handle_request(self):
        with LOCK:
            path = urlparse(self.path)
            size = int(self.headers.get("Content-Length", 0))
            if size > common.MAX_BYTES + 65536:
                return self.reply(413, {"error": "Payload too large"})
            raw = self.rfile.read(size)
            if path.path == "/health":
                return self.reply(200, {"localSimulation": True})
            if path.path == "/__test/scenario":
                SCENARIO.clear()
                SCENARIO.update(json.loads(raw))
                return self.reply(200, {"configured": True})
            if path.path == "/__test/replay":
                return self.reply(200, process(json.loads(raw)["expenseId"]))
            if path.path == "/s3" and self.command == "POST":
                message = BytesParser(policy=default).parsebytes(
                    ("Content-Type: " + self.headers["Content-Type"] + "\r\nMIME-Version: 1.0\r\n\r\n").encode() + raw)
                parts = list(message.iter_parts())
                fields, names = {}, []
                for part in parts:
                    name = part.get_param("name", header="content-disposition")
                    names.append(name)
                    if name != "file":
                        fields[name] = part.get_payload(decode=True).decode()
                try:
                    if not names or names[-1] != "file" or len(names) != len(set(names)):
                        raise ValueError("File must be last; no duplicates")
                    content = parts[-1].get_payload(decode=True)
                    check_post(fields, content)
                except (ValueError, KeyError):
                    return self.reply(403, {"error": "Local S3 policy rejected upload"})
                eid = fields["x-amz-meta-expenseid"]
                result = common.aws("s3").put_object(Bucket=BUCKET, Key=fields["key"], Body=content,
                    ContentType=fields["Content-Type"], Metadata={"userid": fields["x-amz-meta-userid"], "expenseid": eid})
                EVENTS[eid] = {"eventSource": "aws:s3", "eventName": "ObjectCreated:Post", "s3": {
                    "bucket": {"name": BUCKET}, "object": {"key": fields["key"], "versionId": result["VersionId"]}}}
                timer = threading.Timer(0.3, process, [eid])
                timer.daemon = True
                timer.start()
                return self.reply(204)
            tokens = {"Bearer local-alice": "alice", "Bearer local-bob": "bob"}
            user = tokens.get(self.headers.get("Authorization"))
            if not user:
                return self.reply(401, {"error": "Local test identity required"})
            parts = path.path.strip("/").split("/")
            route = "/expenses/{id}" if len(parts) == 2 and parts[0] == "expenses" else path.path
            event = {"version": "2.0", "routeKey": f"{self.command} {route}",
                "requestContext": {"authorizer": {"jwt": {"claims": {"sub": user, "email": user + "@example.com", "email_verified": "true"}}}},
                "pathParameters": {"id": parts[-1]},
                "queryStringParameters": {k: v[0] for k, v in parse_qs(path.query).items()},
                "body": raw.decode() if raw else None}
            result = expense_api.handler(event, None)
            data = json.loads(result["body"])
            if route == "/upload-url" and result["statusCode"] == 200:
                fields = data["upload"]["fields"]
                POLICIES[fields["policy"]] = fields
            return self.reply(result["statusCode"], data)

    do_GET = do_POST = do_PUT = do_DELETE = handle_request


def main():
    os.environ.update(AWS_ACCESS_KEY_ID="testing", AWS_SECRET_ACCESS_KEY="testing", AWS_SESSION_TOKEN="testing",
        AWS_DEFAULT_REGION="ap-southeast-2", AWS_EC2_METADATA_DISABLED="true", EXPENSES_TABLE="Expenses",
        BUDGETS_TABLE="Budgets", BUCKET=BUCKET, PRIVATE_EMAIL_ENABLED="false", ALLOWED_ORIGIN=ORIGIN)
    def forbidden(*args, **kwargs):
        raise AssertionError("Real AWS network transport forbidden")
    with patch.object(botocore.httpsession.URLLib3Session, "send", forbidden), mock_aws(), \
            patch.object(common, "aws", lambda name: Textract() if name == "textract" else REAL_AWS(name)):
        db = boto3.client("dynamodb")
        for name, keys in [("Expenses", ["userId", "expenseId"]), ("Budgets", ["userId"])]:
            db.create_table(TableName=name, BillingMode="PAY_PER_REQUEST",
                AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys],
                KeySchema=[{"AttributeName": k, "KeyType": "HASH" if i == 0 else "RANGE"} for i, k in enumerate(keys)])
        s3 = common.aws("s3")
        s3.create_bucket(Bucket=BUCKET, CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"})
        s3.put_bucket_versioning(Bucket=BUCKET, VersioningConfiguration={"Status": "Enabled"})
        os.environ["TOPIC_ARN"] = common.aws("sns").create_topic(Name="integration-alerts")["TopicArn"]
        print("LOCAL AWS SIMULATION ONLY: http://127.0.0.1:5181", flush=True)
        HTTPServer(("127.0.0.1", 5181), Handler).serve_forever()


if __name__ == "__main__":
    main()
