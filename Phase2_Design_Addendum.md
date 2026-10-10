# Phase 2 design addendum — backend

Status: approved scope implemented locally; no AWS deployment or live service verification.
The original Phase 0/1 documents and diagrams are preserved. This addendum records
the changes authorised after the Stage 1 review. It supersedes conflicting details
in `PROMPT_Phase2_ClaudeCode.md`; that historical prompt is not an execution script.

## Architecture retained

Amplify, Cognito, API Gateway HTTP API, three Python 3.12 Lambdas, two DynamoDB
tables, private S3, Textract AnalyzeExpense, SNS, EventBridge Scheduler and
CloudWatch remain the service architecture. No third table, server, paid external
service or cloud resource has been created. React/Vite/Recharts and SAM are approved
for later stages, but neither frontend nor deployment templates are part of Stage 2.

## API and authentication

All eight Phase 1 routes are retained. `POST /expenses` adds manual creation and
returns 201. Existing routes retain 200 success responses and their established
field names (`total`, `receiptDate`, `monthlyLimit`, `imageKey`, `gst`). New response
fields are additive. See `code/backend/API_CONTRACT.md`.

API Gateway must validate Cognito JWT signature, issuer, audience and expiry. The
Lambda trusts only `requestContext.authorizer.jwt.claims.sub`, not a client-supplied
header/body identity. Direct public invocation of Lambda must not be permitted.
Notification emails must match the verified email claim. Managed login with PKCE
is retained for later frontend integration; Phase 1's ID-token contract is retained.
CORS uses one configured origin; API Gateway preflight is a Phase 3 responsibility.

## Two-table model and financial rules

Expenses retains partition key `userId` and sort key `expenseId` (UUID). Added
attributes include `kind`, `source`, `currency`, `updatedAt`, optimistic `revision`,
and processing lease/version/hash fields. Ordinary records have `kind=EXPENSE`.
Internal `HASH#<sha256>` records in the same user partition reserve identical file
content for one expense ID; they are never returned in expense lists or totals.

Budgets retains its sole key `userId`. Each user has a `months` map, indexed by
`YYYY-MM`, containing `monthlyLimit`, `currency`, `updatedAt` and notification state.
Email and subscription fields remain at the user level. A conditional revision
protects updates from overwriting concurrent changes. There is a 120-budget-month
limit; notification history also consumes this item's 400 KB DynamoDB capacity.
This deliberately simple student-scale design needs archival/restructuring at scale.
The reserved `!SNS_CONTROL` budget item is topic coordination, not a user; valid
Cognito identities cannot address it through the API.

All monetary input, arithmetic and DynamoDB numbers use Decimal. Amounts are
non-negative, at most two decimal places, and capped at AUD 100,000,000. Refunds
and currency conversion are not supported. JSON preserves exact Decimal numeric
literals without float arithmetic. Frontend code must format currency carefully.
Explicit non-AUD receipts/requests fail. Missing receipt currency uses AUD with
`currencySource=application_default` so that assumption is visible.

Dates are ISO `YYYY-MM-DD`; monthly periods use Australia/Sydney. Receipt text is
parsed day-first: `04/11/2024` means 4 November. ISO, day-first hyphens and English
month names with four-digit years are accepted. Missing/invalid merchant, date or
total produces FAILED, never upload-date or fabricated-value substitution. TOTAL
falls back to AMOUNT_PAID only when absent. Optional TAX becomes `gst`.

Totals are calculated from all pages of strongly consistent user-partition queries,
including only PROCESSED AUD expenses. Thus edits, month changes, deletion and
receipt completion do not leave stale stored totals. These paged queries are not
an atomic snapshot across concurrent writes; a fresh read reflects completed edits.
No expense Scan or GSI is required at student scale. Filtered list pages can be
empty while still returning `nextCursor`; callers must continue pagination.

## Receipt upload and safe processing

Presigned POST was already selected in Phase 1; no PUT migration is needed.
Policies require an exact JPEG/PNG Content-Type, exact user/expense metadata and
fixed object key, 1..5,242,880 bytes (5 MiB), and 300-second expiry. Browser checks
are supplementary. S3 cannot prove image contents from MIME alone: processing
checks object size, metadata, image signature and Textract's actual decode result.

**S3 versioning is required.** The first claimed event pins an immutable version;
HEAD, GET and Textract all use it. A later object overwrite is not another expense.
Later event versions are discarded. Lifecycle rules for abandoned uploads and
noncurrent versions are required in Phase 3; deletion explicitly purges all versions
of the exact image key. Private access and encryption remain deployment settings.

State transitions: PENDING -> PROCESSING -> PROCESSED or FAILED. Conditional
revision writes acquire a 90-second processing lease. Active competing invocations
request retry. Expired claims and transient FAILED records can recover on event
replay. A stale worker cannot overwrite a newer claim or deletion. No global lock
serialises receipt processing across unrelated expenses.

SHA-256 reservations prevent identical bytes submitted under different expense IDs
from being charged twice within one user's partition. The same image belonging to
another user is independent. Reservations survive failures/deletion to avoid replay
charges. Recover the original failed record instead of creating a second one.
Different photos/crops of the same paper receipt are not detected as duplicates.

Delete first conditionally writes a DELETED tombstone, then purges S3 versions.
If S3 cleanup fails, the expense remains excluded from totals and DELETE can be
retried. A late upload event for the deleted ID deletes its new object version.
Tombstones and hash reservations remain internal data, so this is not complete
account erasure. No background retry/recovery queue is introduced in Stage 2.
After Lambda's automatic retries are exhausted, an operator must replay the
original S3 event after fixing the cause. A new upload is needed for permanently
invalid images/fields. No public receipt retry route was added.

## Private SNS delivery: fail closed

The existing `expense-alerts` topic is dedicated to user emails. Administrator
alarms must use a separate operational topic in Phase 3; never attach an unfiltered
administrator email to this topic.

1. `PUT /budget` can subscribe only the authenticated user's verified Cognito email.
2. Subscribe supplies `FilterPolicy={"userId":[sub]}`, explicit MessageAttributes
   scope and ReturnSubscriptionArn, including while confirmation is pending.
3. All application subscription changes and private publishing use a conditional
   topic-wide 120-second lease in `!SNS_CONTROL`.
4. Before changing subscriptions, store a 900-second topic-wide publishing freeze.
   Each subscription also requires a recorded age of at least 900 seconds.
5. Before every publish, enumerate every subscription and read its attributes.
   Require confirmed email protocol, correct topic/scope, exactly one user filter,
   and exact matching subscription ARN/email in that user's budget profile.
6. Any unknown, unfiltered, pending, mismatched or unreadable subscription blocks
   **all** private publishing. Missing target and expired coordination lease block
   it too. This intentionally favours privacy over notification availability.
7. `PRIVATE_EMAIL_ENABLED` defaults to false. Phase 3 must restrict topic/subscription
   mutation to the controlled application/operator workflow and verify two-user
   isolation before enabling it. Public self-subscribe, external publishers and
   out-of-band filter changes must be denied. Console maintenance must disable
   publishing first and observe the propagation delay afterward.

Audit reads alone cannot prove data-plane filter propagation or prevent an AWS
administrator from changing SNS after a check. Controlled IAM provisioning is a
required security boundary, not something mocked tests establish. Do not turn on
private publishing merely because unit tests pass. The global lease is intentionally
simple and may suppress/delay notifications at higher concurrency.

Confirmed email subscriptions require clicking the actual SNS confirmation email.
`GET /budget` reports `not_subscribed`, `pending_or_blocked`, or `confirmed`; confirmed
means all application routing checks currently passed, not that email delivery was
observed. Budget saves remain possible without an email subscription.

Budget checking runs after manual creation, edits, deletion, budget changes and
successful receipt processing. Above means strictly greater than the monthly limit.
Notification IDs are stable (`budget:YYYY-MM`, `weekly:YYYY-MM-DD`). Conditional
profile updates claim them before publish. A once-sent alert is not reset by reducing
spending or changing the limit. Routing blocks leave no send claim, permitting a
later check. SNS failures are logged and never roll back an expense.

SNS publish and DynamoDB cannot commit atomically. An uncertain SNS response is
UNKNOWN; a crash after claiming can leave CLAIMED. Neither is automatically resent,
to avoid duplicate alerts. Operator review is required and an email may be missed.
This is not exactly-once delivery; SNS/email can independently duplicate or fail.

## Weekly scheduling and monitoring

Retain `cron(0 9 ? * MON *)`, `Australia/Sydney`, flexible window OFF. Pass
`{"scheduledTime":"<aws.scheduler.scheduled-time>"}` to retain the original reporting
window on retries. The seven days are the preceding Monday through Sunday, local
calendar dates, not the preceding 168 UTC hours. Cross-month weeks show separate
monthly budget comparisons through Sunday. No-spend users receive a clear zero
summary if opted in and routing is verified.

The scheduled batch intentionally pages a Budgets Scan to discover opted-in users;
expense reads remain scoped Queries. Stable weekly IDs prevent application-level
repeat sends. Large populations can exceed the Lambda runtime and need a future
fan-out design. Logs use JSON event names/IDs/counts, not tokens, emails, receipt
text or presigned URLs. Caught business/notification failures appear in logs and
need CloudWatch metric filters; they do not necessarily increment Lambda Errors.

## Deployment implications (preparation only)

Runtime remains Python 3.12. Receipt processing timeout must stay below its 90-second
lease (planned 60 seconds). Notification callers must finish within the 120-second
topic lease; request timeouts/retries are bounded and the lease is checked after
audit. Package dependencies from the lockfile; `tzdata` supports Windows local tests.

Compared with Phase 1, IAM needs SNS ListSubscriptionsByTopic and Publish for the
API, SNS GetSubscriptionAttributes for all notification callers, and conditional
DynamoDB writes for processor/summary coordination. S3 version pinning needs
GetObjectVersion; cleanup needs DeleteObjectVersion and tightly prefix-scoped
ListBucketVersions. Exact policy templates, API authorizer, private encrypted S3,
versioning/lifecycle, retry configuration, logging/alarms and hosting are future
deployment preparation tasks. No claims of deployed IAM enforcement are made.

## References checked during development

- [SNS Subscribe: filters and pending subscription ARN](https://docs.aws.amazon.com/sns/latest/api/API_Subscribe.html)
- [SNS subscription attributes](https://docs.aws.amazon.com/sns/latest/api/API_GetSubscriptionAttributes.html)
- [SNS filter propagation can take 15 minutes](https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html)
- [Scheduler time zones and daylight saving](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html)
- [DynamoDB conditional update expressions](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.UpdateExpressions.html)
