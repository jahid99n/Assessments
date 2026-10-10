# Backend API contract — Stage 2

All routes require API Gateway's Cognito JWT authorizer. Keep the original ID-token
contract and obtain tokens through Cognito managed login/PKCE in the frontend stage.
Never send `userId` in a body/query. JSON errors use `{"error":"message"}`.

| Method | Route | Request / result |
|---|---|---|
| POST | `/expenses` | Required merchant, receiptDate, total; optional gst, category, currency. 201 expense. |
| POST | `/upload-url` | `{"contentType":"image/jpeg"}` or image/png. 200 `{expenseId,upload:{url,fields},expiresIn:300}`. |
| GET | `/expenses` | Optional month, category, from, to, limit (1..100), cursor. 200 `{items,nextCursor?}`. |
| GET | `/expenses/{id}` | 200 expense, with five-minute imageUrl when an image key exists. |
| PUT | `/expenses/{id}` | Nonempty subset of merchant, receiptDate, total, gst, category, currency. 200 updated completed expense. |
| DELETE | `/expenses/{id}` | 200 `{"deleted":true}`. Retry safe; tombstone and image-version cleanup. |
| GET | `/stats` | Optional months (1..24, default 6). 200 `{byCategory,byMonth,thisMonth:{total,budget,remaining,count,currency}}`. |
| GET | `/budget` | Optional month, default Sydney current month. 200 budget, spending, remaining, utilisation and subscription status. |
| PUT | `/budget` | Required monthlyLimit; optional month, currency, verified email, weeklySummary boolean. 200 budget view. |

Money is numeric JSON (or decimal strings on input), AUD only, non-negative with
at most two decimal places. Dates are ISO YYYY-MM-DD. Categories: Groceries, Dining,
Transport, Shopping, Health, Other. Error statuses: 400 input, 401 unauthenticated,
404 missing, 409 concurrent change/invalid state, 413 body too large, 500 service
failure, 503 subscription coordinator busy. Technical AWS messages are not exposed.

`byCategory` describes the current Sydney month; `byMonth` describes the requested
window. Budgets are explicit per month and do not automatically roll forward.
Missing budget displays zero with null utilisation; remaining can be negative.

List order is DynamoDB UUID sort-key order, **not chronological order**. UI should
sort the loaded rows explicitly. Filters apply after reading a bounded page, so
an empty page may include nextCursor. Always continue until the cursor is absent
to load all matches. Cursor ownership is checked; cursors are navigation tokens,
not authorisation credentials. Unfiltered listing includes pending/failed receipts;
date filters exclude receipts with no extracted date. Poll an upload by its ID.

Upload with browser FormData: append every returned field unchanged, then the file
last; let the browser set the multipart boundary. Do not use JSON or presigned PUT.
Poll GET detail for PENDING/PROCESSING/PROCESSED/FAILED. Terminal failure includes
errorMessage and retryable. Processing might outlast the UI polling window; allow
refresh instead of showing a fabricated success/failure. Failed extraction may
require a new corrected photo; transient failure can be replayed by an operator.

Email changes require the JWT email claim to be updated and verified first. A new
subscription causes a topic-wide 15-minute privacy hold. A pending or unsafe other
subscriber can block your emails. Disabling weeklySummary stops future weekly
messages, but does not unsubscribe budget alerts. No separate notification opt-out
API is introduced in these nine routes; SNS's email unsubscribe remains available.

Public expense fields include the original Phase 1 schema plus source, currency,
updatedAt, revision, retryable and (where relevant) currencySource. Internal leases,
hashes and version IDs are not exposed. A presigned image link may return not found
before the upload completes; the UI should show it only when appropriate.
