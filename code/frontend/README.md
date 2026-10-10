# Smart Expense Tracker frontend — Stage 3

React, Vite, JavaScript, Recharts and AWS Amplify Auth. This is the frontend for the existing Stage 2 backend, with the same nine routes. No AWS resources were deployed during this stage.

## Reproduce locally

Use Node.js 22.13 or newer and npm. Development was tested on Windows with Node 24.13.0. From this directory:

```powershell
npm.cmd ci
npm.cmd run demo -- --port 5173 --strictPort
```

Open http://127.0.0.1:5173. On macOS/Linux use `npm` instead of `npm.cmd`. The demo needs no AWS account or credentials. Keep `.env.demo` as provided; do not copy the production environment template to run the demo.

The clearly labelled demo workspace starts signed in with synthetic Australian expenses. You can add, edit, delete and filter expenses, load more records, change monthly budgets, view charts, sign out and enter the demo again. Receipt uploads simulate processing and either success or failure using the outcome selector. No image is sent to AWS or saved in local storage. Demo notifications never send email. Demo records persist in browser local storage; reset them using browser DevTools → Application → Local Storage → delete `smart-expense-demo-v1`, then reload.

## Verification

```powershell
npm.cmd test
npm.cmd run lint
npm.cmd run build
npm.cmd run test:browser
npm.cmd run test:build
```

The browser tests and build checks use installed Microsoft Edge, headless, through Playwright's `msedge` channel. Install Edge if unavailable. Tests start/reuse a local demo server on port 5173; the build verifier briefly starts port 5174. Browser test screenshots and JUnit evidence go to `../../report/`. To regenerate the unit-test evidence:

```powershell
npm.cmd test -- --reporter=default --reporter=junit --outputFile=../../report/stage3-vitest.xml
```

`test:build` must follow a clean, **unconfigured** production build: do not set real `VITE_*` AWS values for this offline check. It checks both rejected development/demo production builds, absence of demo data/code markers in built JavaScript, and disabled authentication when production configuration is missing. No AWS calls are needed. Browser interaction tests block and reject external network requests.

## AWS connection preparation (not executed)

Copy `.env.example` to `.env.local` and replace placeholders only when AWS integration is authorised. Variables exposed through `VITE_*` are public browser configuration, never secrets.

| Variable | Required value |
|---|---|
| `VITE_APP_MODE` | `production` |
| `VITE_API_URL` | HTTPS API Gateway base URL, including stage path if needed |
| `VITE_COGNITO_USER_POOL_ID` | Sydney Cognito user pool ID |
| `VITE_COGNITO_CLIENT_ID` | Public app client ID, with no client secret |
| `VITE_COGNITO_DOMAIN` | Cognito managed-login hostname, without scheme |
| `VITE_REDIRECT_SIGN_IN` | Exact allowed callback URL ending `/auth/callback` |
| `VITE_REDIRECT_SIGN_OUT` | Exact allowed sign-out URL ending `/login` |

Use one consistent origin. The template uses `localhost`; change both redirects to `127.0.0.1` if using that address. Configure Cognito's allowed URLs to match exactly. For deployed hosting use HTTPS URLs. Enable email sign-up and verification in Cognito, authorization code flow, and `openid email profile` scopes. Sign-up, verification and password recovery occur on Cognito's managed page. Both app authentication entry buttons open that page; the user chooses Sign up there.

Amplify handles PKCE, sessions and token refresh. Tokens use session storage rather than persistent local storage. The API client sends the **ID token** as required by the existing backend contract; API Gateway must validate its issuer and app-client audience. Never put AWS keys or a client secret in frontend variables. Session storage remains accessible to JavaScript, so hosting security headers and XSS prevention still matter.

Run `npm.cmd run dev` for an authorised AWS-backed local session, or `npm.cmd run build` to prepare `dist/`. Environment values are embedded at build time. Configure Amplify Hosting to run `npm ci` and `npm run build` in `code/frontend`, publish `dist`, and rewrite application routes to `/index.html` while preserving static assets. No hosting configuration was applied in Stage 3.

API Gateway CORS must permit the actual frontend origin, Authorization and Content-Type headers, and required methods. S3 CORS must permit POST from the same origin. All signed POST fields are submitted unchanged, followed by the file; the Cognito token is never sent to S3. Backend upload policy and object verification remain authoritative for type, size and ownership. Test these settings against real AWS only in a later approved stage.

## User walkthrough

1. **Overview:** inspect monthly AUD spending, budget, remaining amount, expense count, six-month trend, category chart and recent expenses. Text summaries accompany charts.
2. **Expenses:** add a merchant, Australian receipt date, amount, category and optional GST. Edit completed expenses, open details, or confirm deletion. Date/category filters query the backend; merchant search explicitly searches loaded records only. Use Load more for cursor pagination, including when a filtered page is empty.
3. **Receipts:** choose or drop a JPEG/PNG up to 5 MiB. Upload progress is separate from processing status. Polling makes at most 15 attempts with two-second spacing plus request time. If still pending, use Check status. Failed scans provide guidance; there is no pretend successful extraction. Demo processing and failures are visibly simulated.
4. **Budget:** select a month and save its AUD limit. Review spending, remaining amount and over-budget state. In AWS mode request email notifications using the verified account email, then confirm the SNS email. The UI reports backend subscription state; it cannot declare an unverified subscription safe.
5. **Notifications:** weekly summaries require an active verified subscription. Turning weekly summaries off does not unsubscribe budget alerts. Use the SNS email unsubscribe link for removal. Pending or blocked subscriptions require investigation; the Stage 2 backend fails closed.
6. **Sign out:** use the top bar, including on mobile. Real authentication goes through Cognito; demo re-entry is labelled separately.

## Code map and contract

`src/lib/api.js` centralises all nine routes: POST `/expenses`, POST `/upload-url`, GET `/expenses`, GET `/expenses/{id}`, PUT `/expenses/{id}`, DELETE `/expenses/{id}`, GET `/stats`, GET `/budget`, PUT `/budget`. Request contracts are documented in `../backend/API_CONTRACT.md`.

`src/lib/cognito.js` owns authentication; `upload.js` owns S3 POST and polling; `demo.js` provides the offline adapter; `format.js` owns display and client validation. Pages are under `src/pages`; reusable dialogs, tables and controls are under `src/components`. Demo money is calculated in integer cents. Real financial totals remain authoritative backend Decimal values; frontend numbers are for display/charting. AUD is the supported currency.

Production is the default mode. Demo code is imported only in Vite development mode. Production demo builds and builds using a development `NODE_ENV` are rejected. Missing AWS configuration displays a disabled sign-in screen, not mock authentication. Unit tests mock Amplify and fetch; they do not establish live AWS compatibility.

## Known boundaries

- No live Cognito, API Gateway, S3, Textract, SNS or hosting verification yet.
- The existing stats endpoint provides current-month categories and six-month trends, not arbitrary historical dashboard reports.
- No server merchant search, receipt retry endpoint, receipt download URL or dedicated subscription administration endpoint exists; this UI does not invent them.
- Omitting GST on edit preserves an existing value under the current backend contract; the form explains this. Explicit GST removal needs an agreed backend contract change.
- For accurate recent-expense ordering the overview fetches all current-month expense pages before sorting. This is reasonable for a student demo but should become a bounded date-ordered query for large accounts.
- Backend pagination is not a snapshot; concurrent writes can change results between pages. Refresh after uncertain mutation outcomes before retrying.
- Automated accessibility scans cover the four main demo pages and expense modal, not every assistive technology or state.

See `../../report/Stage3_Frontend_Report.md` for observed results and real browser screenshots. Stage 4 and AWS deployment remain subject to approval.
