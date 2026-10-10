# Stage 2 developer notes

## Reproduce on a clean Windows machine

1. Install uv from its official distribution and reopen PowerShell so it is on PATH.
2. Copy/clone this project, keeping the original design files. The inspected copy
   was an exported folder without Git metadata; no upstream branch is assumed.
3. In the project root, run `uv python install 3.12`, then `uv sync --frozen`.
4. Run `uv run --frozen python --version`; this project requires Python 3.12.x.
5. Run `uv run --frozen pytest -q --junitxml=report/stage2-results.xml`.
6. Read the test summary and XML. No AWS account, CLI, real credentials, SAM or
   Docker is needed for these mocked tests. Dependency installation needs internet.

The lockfile fixes boto3, moto, pytest and transitive versions. boto3 and tzdata are
runtime dependencies; pytest/moto are development-only. Package only runtime
dependencies in a later Lambda build. Do not upload the Windows `.venv` to Lambda.

## Understand the backend in demonstration order

1. `expense_api.handler` reads verified API Gateway identity and dispatches one of
   nine routes. Walk through a manual create and the resulting monthly total.
2. `store` separates users through the partition key. Its query iterator follows
   every page; totals are derived from completed records using Decimal.
3. `POST /upload-url` creates PENDING and signs a restricted direct S3 POST.
4. `receipt_processor.handler` handles the S3 event independently. It claims the
   record, verifies the version/metadata, reserves a hash, calls Textract, parses
   fields and conditionally completes the expense.
5. `receipt_parser` shows day-first Australian dates and explicit missing-field
   failures; `categories` shows editable merchant rules.
6. `notifications` checks every topic subscriber before publishing to the intended
   user's filter. Conditional notification IDs suppress application repeat sends.
7. `weekly_summary` uses Sydney calendar dates and stable scheduled-time windows.

Use tests as local evidence, not as a claim of deployed AWS operation. For example:

```powershell
uv run --frozen pytest code/tests/test_api.py -q
uv run --frozen pytest code/tests/test_receipts.py -q
uv run --frozen pytest code/tests/test_notifications.py code/tests/test_weekly.py -q
```

## Configuration and invocation boundaries

`.env.example` is documentation, not an automatically loaded credential file.
Tests install their own environment and block botocore's real HTTP transport.
Outside tests, handlers are real boto3 integrations; do not invoke them against
arbitrary AWS configuration during Phase 2. No local unauthenticated HTTP server
or mock bypass is included in production handlers.

API Gateway is responsible for JWT validation and preflight CORS. Lambda trusts
its verified authorizer context. A forged Lambda test event is not evidence that
JWT validation was tested. API Gateway/Lambda resource policies must prohibit
unauthorised direct invocation when deployment is prepared.

## Failure recovery model

- A transient receipt failure remains visible and is retried by replaying the
  original versioned S3 event. Lambda's asynchronous retry setup belongs to the
  deployment phase. Replays reuse the same user/expense ID and object version.
- If an invocation died while PROCESSING, wait for its 90-second lease to expire.
  The original event can then reclaim the record. Do not edit DynamoDB totals.
- Missing fields, invalid images and non-AUD amounts are terminal failures. Upload
  a corrected photo. The same byte-for-byte image retains its original reservation.
- S3 deletion failure returns a service error after the tombstone has already
  excluded the expense from totals. Repeat DELETE to finish object cleanup.
- Notification routing blocks are logged without consuming the notification ID.
  A later expense/budget operation or original-event replay can retry a budget
  check. There is no independent notification backlog worker in this architecture.
- A weekly run with blocked users reports blocked counts; replay the same
  scheduledTime after correcting subscriptions to retry that reporting period.
- CLAIMED/UNKNOWN notification records require operator investigation. Blindly
  clearing them may resend an email which SNS already accepted.

Full account erasure, a public receipt-retry endpoint, refund support, automatic
exchange rates, OCR accuracy measurement, load tests and deployment verification
are not Stage 2 features. Student-scale aggregation and topic-wide notification
audits are intentionally simple and need a different strategy at large scale.
