"""Every test uses moto, dummy credentials and a hard AWS HTTP transport block."""
import json
from datetime import datetime, timezone
from decimal import Decimal

import boto3
import botocore.httpsession
import pytest
from moto import mock_aws

import common
import expense_api


@pytest.fixture(autouse=True)
def aws_env(monkeypatch):
    for key, value in {"AWS_ACCESS_KEY_ID": "testing", "AWS_SECRET_ACCESS_KEY": "testing", "AWS_SESSION_TOKEN": "testing", "AWS_DEFAULT_REGION": "ap-southeast-2", "AWS_EC2_METADATA_DISABLED": "true", "EXPENSES_TABLE": "Expenses", "BUDGETS_TABLE": "Budgets", "BUCKET": "expense-test-receipts", "PRIVATE_EMAIL_ENABLED": "true", "ALLOWED_ORIGIN": "http://localhost:5173"}.items():
        monkeypatch.setenv(key, value)
    def no_network(*args, **kwargs):
        raise AssertionError("Real AWS HTTP transport is forbidden in tests")
    monkeypatch.setattr(botocore.httpsession.URLLib3Session, "send", no_network)
    monkeypatch.setattr(common, "now", lambda: datetime(2026, 10, 11, 22, 0, tzinfo=timezone.utc))
    with mock_aws():
        db = boto3.client("dynamodb")
        for name, keys in [("Expenses", ["userId", "expenseId"]), ("Budgets", ["userId"])]:
            db.create_table(TableName=name, KeySchema=[{"AttributeName": k, "KeyType": "HASH" if i == 0 else "RANGE"} for i, k in enumerate(keys)], AttributeDefinitions=[{"AttributeName": k, "AttributeType": "S"} for k in keys], BillingMode="PAY_PER_REQUEST")
        s3 = common.aws("s3")
        s3.create_bucket(Bucket="expense-test-receipts", CreateBucketConfiguration={"LocationConstraint": "ap-southeast-2"})
        s3.put_bucket_versioning(Bucket="expense-test-receipts", VersioningConfiguration={"Status": "Enabled"})
        topic = common.aws("sns").create_topic(Name="expense-alerts")["TopicArn"]
        monkeypatch.setenv("TOPIC_ARN", topic)
        yield


@pytest.fixture
def api():
    def call(route, data=None, user="alice", eid=None, query=None, claims=None):
        event = {"routeKey": route, "requestContext": {"authorizer": {"jwt": {"claims": claims if claims is not None else {"sub": user, "email": f"{user}@example.com", "email_verified": "true"}}}}, "queryStringParameters": query, "pathParameters": {"id": eid}, "body": common.encode(data) if data is not None else None}
        result = expense_api.handler(event, None)
        return result["statusCode"], json.loads(result["body"], parse_float=Decimal)
    return call


@pytest.fixture
def expense_data():
    return {"merchant": "Coles", "receiptDate": "2026-10-10", "total": Decimal("40.00"), "gst": Decimal("0.38"), "category": "Groceries", "currency": "AUD"}


@pytest.fixture
def textract_result():
    values = {"VENDOR_NAME": "Coles Supermarkets Australia Pty Ltd", "INVOICE_RECEIPT_DATE": "04/11/2024", "TOTAL": "$40.00", "TAX": "$0.38"}
    return {"ExpenseDocuments": [{"ExpenseIndex": 1, "SummaryFields": [{"Type": {"Text": kind, "Confidence": 99.0}, "ValueDetection": {"Text": value, "Confidence": 97.5}} for kind, value in values.items()], "LineItemGroups": []}]}


@pytest.fixture
def receipt(api):
    def make(user="alice", content=b"\xff\xd8\xffmock-jpeg-for-stubbed-textract", metadata=None, content_type="image/jpeg"):
        _, upload = api("POST /upload-url", {"contentType": content_type}, user=user)
        eid = upload["expenseId"]
        key = upload["upload"]["fields"]["key"]
        obj = common.aws("s3").put_object(Bucket="expense-test-receipts", Key=key, Body=content, ContentType=content_type, Metadata=metadata if metadata is not None else {"userid": user, "expenseid": eid})
        record = {"eventSource": "aws:s3", "eventName": "ObjectCreated:Post", "s3": {"bucket": {"name": "expense-test-receipts"}, "object": {"key": key, "versionId": obj["VersionId"]}}}
        return eid, record
    return make
