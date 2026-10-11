def test_to_only_filter_excludes_undated_pending_receipts(api, expense_data):
    assert api("POST /upload-url", {"contentType": "image/png"})[0] == 200
    assert api("POST /expenses", expense_data)[0] == 201
    status, page = api("GET /expenses", query={"to": "2026-10-31"})
    assert status == 200
    assert len(page["items"]) == 1
    assert page["items"][0]["status"] == "PROCESSED"


def test_upload_and_download_urls_use_sydney_endpoint(api):
    from urllib.parse import urlparse
    _, permission = api("POST /upload-url", {"contentType": "image/jpeg"})
    assert urlparse(permission["upload"]["url"]).hostname == "expense-test-receipts.s3.ap-southeast-2.amazonaws.com"
    _, detail = api("GET /expenses/{id}", eid=permission["expenseId"])
    assert urlparse(detail["imageUrl"]).hostname == "expense-test-receipts.s3.ap-southeast-2.amazonaws.com"
