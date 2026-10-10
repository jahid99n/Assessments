# Stage 2 backend testing report

Review date: 10 October 2026 (Asia/Dhaka). Environment: Windows, Python 3.12.12
provisioned with uv. These are local mocked results, not deployed AWS evidence.

## Final executed result

Command, from the project root:

```powershell
uv run --frozen pytest -q --tb=short --junitxml=report/stage2-results.xml
```

Observed terminal summary: **137 passed in 53.14s**. Failed: **0**. Errors: **0**.
Skipped: **0**. The machine-generated `stage2-results.xml` contains each test name,
outcome and duration. This duration is a local test-suite observation, not an
application latency or AWS performance measurement.

| Test module | Purpose / expected result | Actual observed result | Status |
|---|---|---|---|
| test_api.py (50 cases) | Nine routes; unauthorised/cross-user requests rejected; manual CRUD updates spending; filters/cursors validated; signed upload policy bounded; bad input rejected | 50 passed. CRUD spending assertions verified 40.00 -> 52.10 -> 0; 0.10 + 0.20 remained exactly 0.30 | PASS |
| test_parser.py (31 cases) | Australian dates, leap dates, vendor categories, money parsing, fallback amount, missing fields and currency handling | 31 passed. Coles fixture produced 2024-11-04, AUD 40.00, GST 0.38, Groceries; invalid/missing required fields raised errors | PASS |
| test_receipts.py (19 cases) | Process valid versioned events; prevent event/file duplicates; verify metadata; reject invalid/oversize images; retry transient errors; prevent deleted-record resurrection | 19 passed. Duplicate event called Textract once; duplicate bytes charged once; transient failure recovered; deletion during processing remained deleted | PASS |
| test_notifications.py (15 cases) | Strict budget crossing; once-per-month claims; fail-closed subscriber audits; email verification; topic locking; uncertain SNS delivery | 15 passed. Equal-to-budget did not alert; crossing alerted once; unsafe subscribers caused no publish; SNS failure retained the expense and UNKNOWN state | PASS |
| test_recovery_and_paging.py (13 cases) | Multi-page totals/user enumeration; historical receipt budgets; late confirmation; subscription replacement/resubscription; later-page unsafe subscriber; stale writes and deletion recovery | 13 passed. Three paged expenses totalled 60; weekly retries published no new messages; historical receipt budget checked its own month; stale workers could not commit | PASS |
| test_weekly.py (9 cases) | Seven complete Sydney calendar days, DST transitions, category totals, cross-month comparisons, per-user routing and repeat invocation | 9 passed. Boundary expenses excluded; weekly total 30 with category split 10/20; two users received separately addressed publish requests with their own totals | PASS |

Additional executed checks:

- `uv run --frozen python -m compileall -q code/backend`: exit code 0.
- `uv pip check`: all 30 installed packages compatible, exit code 0.
- Source review found no expense Scan and no float-based financial arithmetic.
  Budgets Scan is deliberate for weekly user enumeration.

## Failure history and corrections

The initial complete run returned **111 passed, 13 failed** in 43.32s. All failures
originated in test setup attempting to set SNS's read-only PendingConfirmation
attribute. The setup was corrected to use moto's default confirmed attribute;
pending confirmation is explicitly simulated in the negative test. No production
privacy check was weakened to make tests pass.

The targeted notification/weekly rerun returned **24 passed** in 12.31s. After
additional integration/recovery cases, a full run returned **136 passed** in 52.55s.
Review then identified the need to resubscribe after a user unsubscribes through
email; that lifecycle fix and regression test are included in the final 137-case run.

## Isolation of tests from real AWS

The autouse fixture starts moto for every test, creates mock DynamoDB/S3/SNS
resources, supplies disposable `testing` credentials in the test process, disables
EC2 metadata access, and patches botocore's real HTTP transport to raise rather
than send a request. Textract uses controlled stubs, including a botocore Stubber
test that checks the exact versioned AnalyzeExpense request/response shape.

The fixture's JPEG/PNG bodies are synthetic signature-prefixed bytes for stubbed
Textract. They are not evidence of image decoding or OCR accuracy. The Coles
response is a synthetic fixture based on the design document's reported values.
No real receipt was scanned, email delivered, or resource deployed by these tests.

## What these tests do not establish

- Cognito sign-up/login or actual API Gateway JWT verification; tests supply the
  verified authorizer context and test backend identity handling.
- S3's real presigned POST policy enforcement, CORS, encryption, event delivery,
  public-access blocking or versioning configuration in a deployed account.
- SNS email confirmation/delivery, data-plane filter propagation or deployed IAM
  isolation. PRIVATE_EMAIL_ENABLED remains false in the environment template.
  Verified routing must be tested with two real users only in the authorised
  deployment phase, after restricting out-of-band subscription mutations.
- Real DynamoDB distributed concurrency. Tests exercise conditional stale writes,
  active/expired claims and controlled interleavings; they are not a load test.
- Exactly-once SNS delivery. UNKNOWN/CLAIMED notifications require review, and
  either missing or duplicate downstream email remains possible.
- Perceptual receipt duplication: only identical file bytes per user are detected.
- Automatic recovery after AWS retry exhaustion; original-event replay is an
  operator task. There is no independent notification backlog processor.
- Atomic snapshots across multiple query pages, large-user batch completion,
  currency conversion, refunds, full account erasure, or measured operating cost.
- Frontend functionality, SAM validation, deployment, screenshots or production
  readiness. Those stages have not been started.

## Stage 3 handoff

The nine-route contract is documented in `code/backend/API_CONTRACT.md`; local
setup and failure recovery are documented in `code/backend/LOCAL_DEVELOPMENT.md`.
The frontend can now be implemented against these contracts after user approval.
Respect pagination, explicit processing failures, AUD rules, and notification
`pending_or_blocked` states. Do not equate an upload finishing with OCR completing.
