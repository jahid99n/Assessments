# Smart Expense Tracker — ICT5205 Assignment 3

AWS serverless expense tracking with receipt extraction. **Stage 2 backend only:**
implemented and tested locally with mocked AWS; no frontend or deployed service yet.

The architecture uses Amplify Hosting, Cognito, API Gateway, Lambda, DynamoDB, S3,
Textract, SNS, EventBridge Scheduler and CloudWatch. Three Lambda handlers separate
authenticated API requests, asynchronous receipt processing, and weekly reporting.
Read `Phase1_Design.md` together with `Phase2_Design_Addendum.md` for the approved
design and its operational limitations.

## Local backend setup (PowerShell)

Install Git (optional for this exported project folder) and uv. No AWS account or
credentials are needed for tests. From this project directory:

```powershell
uv python install 3.12
uv sync --frozen
uv run --frozen python --version
uv run --frozen pytest -q
```

uv creates `.venv` using Python 3.12 and installs the exact dependencies in `uv.lock`.
Alternatively, after uv sync: `.\.venv\Scripts\python.exe -m pytest -q`.
There is no need to activate the environment or change PowerShell execution policy.

Every test runs inside moto, uses in-memory dummy credentials, and blocks the real
botocore HTTP transport. Textract is stubbed; fixtures are synthetic, not measured
OCR evidence. Do not remove the transport block to make a failing test pass.

## Files

- `code/backend/`: Lambda handlers and small shared modules; see `API_CONTRACT.md`.
- `code/tests/`: pytest tests for routes, parsing, receipts, SNS isolation and weeks.
- `report/Stage2_Testing_Report.md`: executed results and known evidence limits.
- `Phase2_Design_Addendum.md`: approved corrections and deployment prerequisites.
- `.env.example`: configuration names, not credentials; tests set their own values.
- Existing `diagram_src/`, `images/` and Phase 0/1 documents are preserved.

## Lambda entry points (future deployment)

| Function | Handler |
|---|---|
| expense-api | `expense_api.handler` |
| receipt-processor | `receipt_processor.handler` |
| weekly-summary | `weekly_summary.handler` |

The backend folder must be at the package root alongside its dependencies. Runtime
is Python 3.12. Required environment variables: EXPENSES_TABLE, BUDGETS_TABLE,
BUCKET, TOPIC_ARN; region defaults to ap-southeast-2. ALLOWED_ORIGIN configures the
response origin. Private email is disabled unless PRIVATE_EMAIL_ENABLED=true;
read the addendum before enabling it in any real environment.

S3 versioning is mandatory. API Gateway must authenticate every route. Lambda
roles must be the only permitted application mutation path. Future SAM templates
will provision these settings; no deployment command is provided or run in Stage 2.

Stage 3 frontend, demo mode, comprehensive manuals and deployment preparation are
pending separate approval. This directory currently has no `.git` metadata; no
commit, branch switch or push was performed.
