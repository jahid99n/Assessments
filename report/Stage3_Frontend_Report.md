# Stage 3 frontend completion and testing report

Recorded 10 October 2026 in the development environment (Asia/Dhaka). Sydney dates shown by the application can be the following day. This report covers local frontend development only. No deployment, paid AWS API invocation, repository push or Stage 4 integration run was performed.

## Scope and implementation

The existing Phase 1 design, Stage 2 addendum and backend API contract were inspected before implementation. Original backend and project documents were preserved. This workspace has no Git repository metadata, so no Git diff or commit evidence is claimed.

The new `code/frontend` application provides:

- A responsive navy/teal dashboard with four summary cards, category chart, six-month trend, budget progress and recent expenses.
- Expense creation, editing, detail inspection, confirmation before deletion, date/category filters, cursor pagination and explicitly loaded-record-only merchant search.
- JPEG/PNG selection and drag/drop, 5 MiB validation, presigned multipart POST, upload progress, bounded receipt polling, pending/processing/completed/failed states, cancellation and manual status recheck.
- Month-specific AUD budgets, utilisation and overspend display, backend subscription status and weekly-summary controls with confirmation guidance.
- Cognito managed authentication through Amplify, authorization code/PKCE, refreshed ID tokens, session storage, protected routes, sign-out and authentication/configuration error handling.
- Explicit demo mode with persistent synthetic records, working local CRUD/budgets/charts and simulated receipt outcomes. No demo image upload or email delivery occurs.
- Native accessible dialogs with focus handling, labelled controls, focus outlines, accessible chart summaries, loading/error/empty states and desktop/tablet/mobile navigation.

## Added structure

```text
code/frontend/
  README.md, package.json, package-lock.json
  .env.example, .env.demo, .gitignore
  index.html, vite.config.js, eslint.config.js, playwright.config.js
  src/
    main.jsx, App.jsx, runtime.jsx, config.js, styles.css
    components/{Icon,UI,Expenses}.jsx
    pages/{Dashboard,ExpensesPage,ReceiptPage,BudgetPage}.jsx
    lib/{api,cognito,demo,format,upload}.js
  tests/
    app.test.jsx, services.test.js, cognito.test.js, setup.js
    build-verification.mjs
  browser-tests/
    dashboard.spec.js, accessibility.spec.js
  dist/                         local generated production build
report/
  Stage3_Frontend_Report.md
  stage3-vitest.xml
  stage3-browser-results.xml
  stage3-build-checks.json
  stage3-screenshots/
    dashboard-desktop.png
    dashboard-mobile.png
    receipt-demo-completed.png
```

Dependencies are recorded in the lockfile; use `npm ci` to reproduce. Generated node_modules, dist and local environment files are ignored by the frontend's Git ignore rules.

## Actual validation results

Executed with Node 24.13.0, npm 11.6.2, Vitest 5.0.3, Vite 8.3.4 and installed Microsoft Edge through Playwright. All financial data seen in browser tests was explicitly simulated.

| Test suite/check | Purpose and expected result | Observed final result | Status |
|---|---|---|---|
| `services.test.js` | Nine API methods/URLs, token and error handling, empty-page cursor continuation, validation, cents calculations, multipart upload, polling and demo separation | 41 passed, 0 failed | PASS |
| `app.test.jsx` | Rendering, authentication guards, CRUD, filters/pagination, budgets, receipt validation and error states | 19 passed, 0 failed | PASS |
| `cognito.test.js` | Mocked SDK configuration, code flow, session storage, ID token, session/Hub and sign-out behavior | 7 passed, 0 failed | PASS |
| `dashboard.spec.js` | Actual Edge desktop rendering, CRUD/dialog focus, budget persistence, receipt outcomes, mobile and tablet navigation; reject external calls/runtime errors | 6 passed, 0 failed | PASS |
| `accessibility.spec.js` | Axe WCAG 2 A/AA and 2.1 A/AA scans: overview, expenses, receipts, budget and expense modal | 5 passed, 0 failed; no violations reported in these scans | PASS |
| ESLint | No lint errors | Exit 0 | PASS |
| Production build | Generate deployable static files without demo mode | Exit 0 | PASS |
| Build verifier | Reject demo build; reject development NODE_ENV bypass; exclude demo adapter/data markers; fail closed in Edge with missing AWS config | 4 checks passed, 0 failed | PASS |

**Automated test total: 78 passed, 0 failed** (67 Vitest + 11 Playwright). Four additional production-safety checks passed. Final Vitest run: 7.13 seconds. Final browser run: 26.0 seconds. These are local test durations, not application performance benchmarks. Backend tests were not rerun in this frontend stage; no new backend test result is claimed.

Evidence: [Vitest JUnit](stage3-vitest.xml), [Playwright JUnit](stage3-browser-results.xml), [build checks](stage3-build-checks.json). Each JUnit file contains individual test names and observed outcomes.

Earlier development runs exposed and resolved: an unsupported CSS data import; ambiguous test fixtures/labels; missing modal initial focus; mobile horizontal overflow; low-contrast secondary text; and ESLint's missing `.mjs` globals configuration. Final results above are from successful executions after the relevant corrections. A large initial JavaScript chunk was reduced by lazy-loading the dashboard/chart module.

The final production build emitted CSS 23.23 kB, main JavaScript 299.97 kB, dashboard JavaScript 378.28 kB, and Cognito JavaScript 78.48 kB (uncompressed sizes reported by Vite). No demo adapter or synthetic seed markers were found in production JavaScript. This does not constitute deployment or live authentication evidence.

## Actual screenshots

These are unmodified captures from the local Edge browser displaying labelled demo data, not AWS screenshots:

- [Desktop overview](stage3-screenshots/dashboard-desktop.png)
- [Mobile overview](stage3-screenshots/dashboard-mobile.png)
- [Simulated completed receipt](stage3-screenshots/receipt-demo-completed.png)

The mobile image is a full-page capture; fixed navigation appears at its viewport position. Browser viewport assertions separately verified no document-level horizontal overflow at mobile and tablet sizes.

## API integration and architecture

All nine existing API routes are mapped without backend changes:

| Method | Route | Frontend use |
|---|---|---|
| POST | `/expenses` | Manual entry |
| POST | `/upload-url` | Presigned POST preparation |
| GET | `/expenses` | Filtered cursor pagination |
| GET | `/expenses/{id}` | Details and receipt status |
| PUT | `/expenses/{id}` | Edit allowed fields |
| DELETE | `/expenses/{id}` | Confirmed deletion |
| GET | `/stats` | Dashboard cards and charts |
| GET | `/budget` | Selected-month budget |
| PUT | `/budget` | Budget and subscription preferences |

The API adapter uses the established field names and ID-token contract. Uploads preserve every signed POST field and append the file last, with no Authorization token sent to S3. API failures are not silently replaced with demo responses. Mutation requests are not automatically retried because an interrupted response does not prove that the backend failed to save the change.

No cloud architecture changes or additional AWS services/tables were introduced. Frontend-only implementation decisions are: managed Cognito authentication rather than custom password forms; development-only demo adapter; integer cents in local demo calculations; bounded receipt polling with manual recheck; and lazy chart loading. The Phase 2 design addendum remains the backend source of truth.

## Limitations and AWS readiness

The frontend is ready for review and the next approved integration stage. It is **not verified against deployed AWS**. SDK authentication tests use mocks. The following require later testing/configuration:

1. Cognito public client, email sign-up/verification, allowed callback/sign-out URLs, scopes, PKCE flow and real token expiry/refresh. Verify API Gateway accepts the specified ID-token issuer/audience.
2. Actual API/S3 CORS and private bucket upload policies; real S3 event processing, Textract output, eventual receipt completion and browser failure recovery.
3. SNS confirmation, filtering and fail-closed subscriber isolation under real subscriptions, including pending/blocked topic conditions. The UI merely displays backend status and cannot verify subscription safety independently. Weekly opt-out does not unsubscribe budget alerts.
4. Amplify SPA rewrites, public build variables, HTTPS, appropriate security headers and cache behavior. Session storage does not protect tokens from XSS.
5. Backend limitations: no server merchant search, explicit GST-clear semantics, receipt reprocessing/download URL, or dedicated subscription-management endpoint. The UI describes or respects those boundaries.
6. Current-month recent records require following all expense pages then sorting; large-account efficiency needs a bounded date-ordered backend query. Pagination is not a consistent snapshot across concurrent writes.
7. Accessibility automation covers selected rendered states and does not replace manual screen-reader testing. No claim is made about browsers other than the tested Edge environment.

See [frontend README](../code/frontend/README.md) for clean installation, test commands, configuration and a user walkthrough. Stage 3 ends here; Stage 4 and AWS deployment await approval.
