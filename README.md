# Smart Expense Tracker — ICT5205 Assignment 3

AWS serverless expense tracking with receipt extraction. **Stage 4: local integration
and deployment preparation.** The Python backend and React frontend are implemented;
local full-stack tests use simulated AWS. Infrastructure is prepared but nothing
has been deployed. Live AWS deployment requires explicit approval.

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
- `code/frontend/`: React/Vite dashboard, Cognito adapter and explicit offline demo.
- `code/integration/` and `code/frontend/integration/`: localhost-only full-stack test harness; never deploy.
- `infrastructure/template.yaml`: SAM/CloudFormation, Sydney, private email disabled by default.
- `amplify.yml`, `customHttp.yml`: prepared static hosting build and security headers.
- `report/Stage4_Integration_Testing_Report.md`: current executed evidence and limitations.
- `report/AWS_Deployment_Guide.md`: installation, approval-gated deployment, verification and cleanup.
- `report/AWS_Cost_Estimate.md`, `report/Security_Review.md`: assumptions, controls and live verification gates.
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

S3 versioning is mandatory. API Gateway authenticates every route in the prepared
template. Application roles must be the controlled mutation path. The deployment
guide contains future commands, but none were executed during local development.

## Frontend and integration testing

From project root:

```powershell
Set-Location code/frontend
npm.cmd ci
npm.cmd run demo
```

Open http://127.0.0.1:5173. This development-only demo uses labelled synthetic data
and local storage, not AWS. Stop the development server with Ctrl+C when finished.
See [frontend instructions](code/frontend/README.md) for Cognito configuration and
the user walkthrough. Production builds reject demo mode and contain no test harness.

From `code/frontend`, run these checks sequentially:

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run test:browser
npm.cmd run test:integration
npm.cmd run build
npm.cmd run test:build
```

Browser checks require installed Microsoft Edge. Full-stack integration automatically
starts localhost frontend/backend servers on ports 5180/5181. The real React API
adapter, Python API, receipt parser/processor and DynamoDB access code execute; only
AWS boundaries are simulated. No real JWT verification or OCR accuracy is claimed.
Run production build checks before adding actual AWS variables to `.env.local`.

From project root, validate the infrastructure without an AWS account:

```powershell
uv run --frozen cfn-lint infrastructure/template.yaml --region ap-southeast-2
```

SAM CLI/container validation remains a deployment prerequisite; consult the
[deployment guide](report/AWS_Deployment_Guide.md). Preserve both the original
design and [Stage 4 addendum](Phase4_Integration_Addendum.md). Source changes are
tracked on branch `main`; no AWS deployment has been performed. The
[IAM preparation guide](infrastructure/iam/README.md) supplies the scoped deployment
policies, administrator setup steps and commands for the dedicated execution role.
