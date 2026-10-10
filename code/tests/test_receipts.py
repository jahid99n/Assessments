from copy import deepcopy
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError
from botocore.stub import Stubber

import common
import receipt_processor as processor
import store


def stub_textract(monkeypatch, response):
    original = common.aws
    client = Mock()
    client.analyze_expense.return_value = response
    monkeypatch.setattr(common, "aws", lambda name: client if name == "textract" else original(name))
    return client


def test_valid_receipt_and_duplicate_event(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    assert processor.handler({"Records": [event]}, None)["outcomes"] == ["PROCESSED"]
    assert processor.process(event) == "ALREADY_PROCESSED"
    assert tx.analyze_expense.call_count == 1
    item = store.get("alice", eid)
    assert item["receiptDate"] == "2024-11-04" and item["total"] == 40
    assert store.total("alice", "2024-11") == 40
    assert tx.analyze_expense.call_args.kwargs["Document"]["S3Object"]["Version"] == event["s3"]["object"]["versionId"]


def test_real_botocore_textract_contract(receipt, textract_result, monkeypatch):
    _, event = receipt()
    tx = common.aws("textract")
    original = common.aws
    monkeypatch.setattr(common, "aws", lambda name: tx if name == "textract" else original(name))
    obj = event["s3"]["object"]
    with Stubber(tx) as stub:
        stub.add_response("analyze_expense", textract_result, {"Document": {"S3Object": {"Bucket": "expense-test-receipts", "Name": obj["key"], "Version": obj["versionId"]}}})
        assert processor.process(event) == "PROCESSED"
        stub.assert_no_pending_responses()


def test_duplicate_bytes_new_upload(receipt, textract_result, monkeypatch):
    first, event = receipt()
    second, duplicate = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    processor.process(event)
    assert processor.process(duplicate) == "FAILED"
    assert "Duplicate" in store.get("alice", second)["errorMessage"]
    assert store.total("alice", "2024-11") == 40
    assert tx.analyze_expense.call_count == 1


def test_duplicate_detection_is_user_scoped(receipt, textract_result, monkeypatch):
    _, a = receipt()
    _, b = receipt(user="bob")
    stub_textract(monkeypatch, textract_result)
    assert processor.process(a) == processor.process(b) == "PROCESSED"
    assert store.total("alice", "2024-11") == store.total("bob", "2024-11") == 40


@pytest.mark.parametrize("metadata", [{}, {"userid": "bob", "expenseid": "wrong"}])
def test_wrong_metadata(receipt, textract_result, monkeypatch, metadata):
    eid, event = receipt(metadata=metadata)
    tx = stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "FAILED"
    assert "ownership" in store.get("alice", eid)["errorMessage"]
    tx.analyze_expense.assert_not_called()


def test_invalid_image(receipt, textract_result, monkeypatch):
    eid, event = receipt(content=b"not-an-image")
    tx = stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "FAILED"
    assert store.get("alice", eid)["retryable"] is False
    tx.analyze_expense.assert_not_called()


def test_png_receipt(receipt, textract_result, monkeypatch):
    _, event = receipt(content=b"\x89PNG\r\n\x1a\nmock", content_type="image/png")
    stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "PROCESSED"


def test_size_rechecked_server_side(receipt, textract_result, monkeypatch):
    eid, event = receipt(content=b"\xff\xd8\xff" + b"x" * common.MAX_BYTES)
    tx = stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "FAILED"
    tx.analyze_expense.assert_not_called()


def test_missing_total_visible_failure(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    textract_result["ExpenseDocuments"][0]["SummaryFields"] = textract_result["ExpenseDocuments"][0]["SummaryFields"][:2]
    stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "FAILED"
    assert store.get("alice", eid)["status"] == "FAILED"
    assert store.total("alice", "2024-11") == 0


def test_textract_transient_error_recovers(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    tx.analyze_expense.side_effect = [ClientError({"Error": {"Code": "ThrottlingException", "Message": "retry"}}, "AnalyzeExpense"), textract_result]
    with pytest.raises(RuntimeError):
        processor.handler({"Records": [event]}, None)
    assert store.get("alice", eid)["status"] == "FAILED"
    assert store.get("alice", eid)["retryable"] is True
    assert processor.process(event) == "PROCESSED"
    assert store.total("alice", "2024-11") == 40


def test_active_lease_and_expired_recovery(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    item = store.get("alice", eid)
    store.replace({**item, "status": "PROCESSING", "leaseUntil": int(common.now().timestamp()) + 10}, 0)
    with pytest.raises(RuntimeError):
        processor.process(event)
    item = store.get("alice", eid)
    store.replace({**item, "leaseUntil": 0}, item["revision"])
    stub_textract(monkeypatch, textract_result)
    assert processor.process(event) == "PROCESSED"


def test_db_final_write_failure_retries_without_double_charge(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    stub_textract(monkeypatch, textract_result)
    original = processor.finish
    attempts = 0
    def fail_once(item, changes):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "retry"}}, "PutItem")
        return original(item, changes)
    monkeypatch.setattr(processor, "finish", fail_once)
    with pytest.raises(RuntimeError):
        processor.handler({"Records": [event]}, None)
    assert store.total("alice", "2024-11") == 0
    assert processor.process(event) == "PROCESSED"
    assert store.total("alice", "2024-11") == 40


def test_db_claim_failure_does_not_call_textract(receipt, textract_result, monkeypatch):
    _, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    monkeypatch.setattr(store, "replace", Mock(side_effect=RuntimeError("database unavailable")))
    with pytest.raises(RuntimeError):
        processor.handler({"Records": [event]}, None)
    tx.analyze_expense.assert_not_called()


def test_overwrite_cannot_change_processed_receipt(receipt, textract_result, monkeypatch):
    eid, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    processor.process(event)
    key = event["s3"]["object"]["key"]
    version = common.aws("s3").put_object(Bucket="expense-test-receipts", Key=key, Body=b"replacement")["VersionId"]
    replacement = deepcopy(event)
    replacement["s3"]["object"]["versionId"] = version
    assert processor.process(replacement) == "IGNORED_VERSION"
    assert store.get("alice", eid)["total"] == 40
    assert tx.analyze_expense.call_count == 1


def test_delete_while_processing_never_resurrects(api, receipt, textract_result, monkeypatch):
    eid, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    def delete_during_textract(**kwargs):
        assert api("DELETE /expenses/{id}", eid=eid)[0] == 200
        return textract_result
    tx.analyze_expense.side_effect = delete_during_textract
    with pytest.raises(common.Problem):
        processor.process(event)
    assert store.get("alice", eid, internal=True)["status"] == "DELETED"
    assert store.total("alice", "2024-11") == 0
    assert processor.process(event) == "DELETED"


@pytest.mark.parametrize("change", ["bucket", "key", "mapping"])
def test_bad_event_mapping(receipt, textract_result, monkeypatch, change):
    _, event = receipt()
    tx = stub_textract(monkeypatch, textract_result)
    if change == "bucket":
        event["s3"]["bucket"]["name"] = "another-bucket"
    elif change == "key":
        event["s3"]["object"]["key"] = "receipts/../../invalid"
    else:
        event["s3"]["object"]["key"] = event["s3"]["object"]["key"].replace("alice", "bob")
    assert processor.process(event) == "REJECTED"
    tx.analyze_expense.assert_not_called()
