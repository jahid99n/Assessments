# Prompt for Claude Code (VS Code) – Phase 2

Copy everything inside the box below into Claude Code.

---

```
You are helping my group build ICT5205 Cloud Computing Assignment 3: "Smart Expense Tracker",
a serverless AWS app where users upload receipt photos, Amazon Textract reads merchant/date/total/GST,
results are stored in DynamoDB and shown on a web dashboard with charts, and SNS emails budget alerts
and a weekly summary.

## Read these first (do not skip)
1. Assignment3_ExpenseTracker/Phase0_Decisions.md  – decisions, services, budget rules
2. Assignment3_ExpenseTracker/Phase1_Design.md     – FULL design: architecture, DynamoDB tables,
   S3 layout, API routes with request/response, Lambda steps, IAM, security, front-end layout
3. Assignment3_ExpenseTracker/images/architecture.png – architecture diagram
Follow the design exactly. If you think the design must change, ask me first and explain why.

## Rules
- Do NOT deploy anything to AWS and do NOT run any AWS CLI command that creates/changes resources.
  This phase is local only. No AWS credentials are needed.
- Never put AWS keys, account IDs or secrets in code or git.
- Work step by step. Before each step, tell me in 2–3 lines what you will do, then do it.
  Stop and check in with me after: (a) backend done + tests passing, (b) front end done.
- Keep the code simple and well commented – this is a student project and we must explain
  every line to the examiner.
- Region is ap-southeast-2 (Sydney). Python 3.12 for Lambda. No frameworks on the front end.

## Phase 2 tasks

### Step 1 – Folder structure (inside Assignment3_ExpenseTracker/)
code/
  backend/
    common.py              shared helpers (JSON responses, CORS headers, Decimal handling, logging)
    expense_api.py         handler = expense_api.handler
    receipt_processor.py   handler = receipt_processor.handler
    weekly_summary.py      handler = weekly_summary.handler
    categories.py          rule-based categories (Phase1_Design.md section 4.4)
    requirements.txt       (boto3 is already in Lambda – keep empty or dev-only)
  frontend/
    index.html, dashboard.html, styles.css, config.js, auth.js, api.js, app.js, mock-api.js
  tests/
    test_expense_api.py, test_receipt_processor.py, test_weekly_summary.py,
    test_categories.py, conftest.py, requirements-dev.txt (pytest, moto[dynamodb,s3,sns], boto3)
deploy/
  build.py                 creates deploy/dist/expense-api.zip, receipt-processor.zip,
                           weekly-summary.zip (each = handler file + common.py + categories.py)
                           and deploy/dist/frontend.zip for Amplify manual deploy
  README.md                what each zip is and where it goes in Phase 3
images/                    (report images only)

### Step 2 – Backend (Lambda, Python 3.12, boto3)
Environment variables: EXPENSES_TABLE, BUDGETS_TABLE, BUCKET, TOPIC_ARN, ALLOWED_ORIGIN.
expense_api.py – API Gateway HTTP API payload v2.0, route on event["routeKey"]:
  POST /upload-url        create PENDING expense, return S3 presigned POST
                          (key receipts/{userId}/{expenseId}.jpg, 5 min expiry,
                          content-length-range 1..5 MB, Content-Type starts-with image/)
  GET /expenses?month=YYYY-MM, GET /expenses/{id} (+ presigned GET imageUrl),
  PUT /expenses/{id} (only merchant, receiptDate, total, gst, category editable),
  DELETE /expenses/{id} (also delete the S3 object),
  GET /stats?months=6 (byCategory, byMonth, thisMonth {total, budget, remaining}),
  GET /budget, PUT /budget (save; sns.subscribe email with FilterPolicy {"userId":[id]}
                          when email is new; unsubscribe old one).
  userId ALWAYS from event["requestContext"]["authorizer"]["jwt"]["claims"]["sub"].
  Validate input; return 400/404/500 as {"error": "..."}; include CORS headers.
receipt_processor.py – S3 ObjectCreated event:
  parse userId/expenseId from key (URL-decode it), call textract.analyze_expense,
  take VENDOR_NAME, INVOICE_RECEIPT_DATE, TOTAL (fallback AMOUNT_PAID), TAX.
  Clean money ("$1,234.50" -> Decimal). Parse dates DAY-FIRST (Australian: 04/11/2024 = 2024-11-04),
  also accept YYYY-MM-DD, DD-MM-YYYY, "4 Nov 2024"; if none, use today.
  Set category, confidence, status PROCESSED (or FAILED + errorMessage if no total).
  Then sum this month's PROCESSED totals; if > monthlyLimit and lastAlertMonth != this month,
  sns.publish with MessageAttributes userId, and set lastAlertMonth.
weekly_summary.py – scan Budgets where weeklySummary = true, query each user's last 7 days,
  publish a short plain-text summary (total, number of receipts, top category, % of budget).
Use Decimal for all money in DynamoDB. Log JSON lines for CloudWatch.

### Step 3 – Tests (must pass before moving on)
Use pytest + moto (mock_aws) for DynamoDB, S3, SNS. Textract is NOT supported by moto –
stub it with botocore.stub.Stubber or monkeypatch, using a realistic AnalyzeExpense response
based on a Coles receipt: VENDOR_NAME "Coles Supermarkets Australia Pty Ltd",
INVOICE_RECEIPT_DATE "04/11/2024", TOTAL "$40.00", TAX "$0.38".
Test at least: each API route (happy path + one error), user isolation (user A cannot read
user B's expense), date parsing cases, money parsing, categories, budget alert sent once per
month, FAILED status when no total, weekly summary message.
Show me the pytest output.

### Step 4 – Front end (plain HTML/CSS/JS, Chart.js from cdnjs with a pinned version)
- config.js: API_URL, COGNITO_DOMAIN, CLIENT_ID, REDIRECT_URI, REGION, and MOCK_MODE (true by default).
- auth.js: Cognito managed login using Authorization Code + PKCE (crypto.subtle SHA-256),
  token exchange at {COGNITO_DOMAIN}/oauth2/token, store tokens in sessionStorage, logout URL.
  Send the ID token as "Authorization: Bearer <token>".
- api.js: fetch wrapper; when MOCK_MODE is true use mock-api.js instead (fake data in
  localStorage, fake 2-second "processing" after upload) so the whole dashboard works
  on my laptop with no AWS.
- dashboard.html layout as in Phase1_Design.md section 8: 4 summary cards, Upload receipt
  button (5 MB / jpeg/png check, upload with presigned POST via FormData, then poll
  GET /expenses/{id} every 2 s up to 30 s), pie chart by category, bar chart by month,
  expenses table with month filter + View image / Edit / Delete, settings form for budget,
  email, weekly summary checkbox.
- Australian formats: dates DD/MM/YYYY, currency AUD ($). Responsive (works on phone).
- Clean, simple design; accessible colours; no build tools.
Tell me how to open it locally (e.g. VS Code "Live Server" extension, or
`python -m http.server 5500` inside code/frontend) and what I should see.

### Step 5 – Packaging
deploy/build.py builds the 4 zips into deploy/dist/ (add deploy/dist/ to .gitignore).
deploy/README.md: table of zip -> AWS service -> handler -> env vars -> timeout/memory,
copied from Phase1_Design.md section 6.

### Step 6 – Finish
- Add a short Assignment3_ExpenseTracker/README.md (project summary, folder map,
  how to run tests, how to run the front end in mock mode).
- Commit with clear messages and push to the current branch.
- Give me a summary: what was built, test results, anything I need to decide,
  and what Phase 3 (AWS console setup) will involve.
```

---

## How to use it
1. Install **VS Code** and the **Claude Code** extension (Extensions panel → search "Claude Code" → Install), then sign in.
2. Get the project:
   ```
   git clone https://github.com/jahid99n/NLP.git
   cd NLP
   git checkout claude/beautiful-franklin-3dxyb1
   ```
3. Open the `NLP` folder in VS Code (File → Open Folder).
4. Install Python 3.12+ (needed for the tests).
5. Open Claude Code (Claude icon in the sidebar), paste the prompt above, press Enter.
6. Approve its steps as it asks; review the test output and dashboard screenshots at each check-in.
