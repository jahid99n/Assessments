# Stage 4 security review

Review date: 11 October 2026. Scope: source, local execution and infrastructure configuration. **No live AWS security verification has occurred.** The offline harness does not validate real JWT signatures or emulate complete AWS IAM/S3/SNS enforcement.

## Controls and evidence

| Boundary | Implementation / verification | Remaining live check |
|---|---|---|
| Authentication | SAM HTTP API default Cognito JWT authorizer on all nine routes; issuer and client audience set. Cognito public client, code flow, email verification, token revocation, no implicit flow/client secret. Backend trusts only authorizer claims. | Real managed login/PKCE, expired/wrong-issuer/wrong-audience/missing JWT rejection, refresh and sign-out. |
| User isolation | Partition-scoped DynamoDB Queries/GetItem; no client userId accepted. Cross-user GET/PUT/DELETE, lists and cursors have tests. | Test two independent real accounts and IAM restrictions on direct Lambda/data access. |
| Receipt uploads | Exact signed key, owner/expense metadata, JPEG/PNG type, 1..5,242,880-byte POST policy, 300-second expiry. Private encrypted versioned bucket; pinned versions and duplicate hash reservations. | Real S3 policy expiry/size/type/metadata enforcement, CORS, object events and valid-image decoding. |
| Financial integrity | Decimal arithmetic, AUD only, ISO dates, day-first extraction, derived completed-expense totals, conditional revisions and leases. | Real concurrent invocation/load tests; paged totals are not an atomic snapshot. |
| SNS privacy | Audit all subscriptions, exact user filter and stored verified email/ARN, confirmation and 15-minute hold, topic lock; publish disabled by default. Tests assert no publish for unsafe subscriptions. | IAM/account governance, eventual filter propagation and actual two-inbox isolation. |
| IAM | Function-specific actions/resources, receipt prefix scope, no expense Scan; only weekly Lambda scans Budgets. Textract AnalyzeExpense uses `*` because it lacks resource-level scoping. | Account permissions boundaries/SCPs and actual service authorization. Lambda roles necessarily access multiple users; application identity checks are essential. |
| CORS | Single exact HTTPS frontend origin for API and S3, no wildcard origin, limited methods/headers. | Verify preflight and upload from deployed origin; CORS does not replace authorization. |
| Browser | Production defaults, missing configuration fails closed; build rejects demo/development bypass; tokens in session storage; HTML escapes values; prepared hosting headers. | Apply and inspect headers, CSP compatibility, XSS review and real auth navigation. Session storage remains accessible to JavaScript. |
| Logging/errors | Sanitised API errors; structured event identifiers; no financial payload, email, JWT or upload-policy logging. Four log groups retained 14 days. | Verify actual logs contain no secrets; restrict log readers. |
| Test isolation | Fixed dummy credentials, blocked botocore transport, moto and stubbed Textract; localhost HTTP servers; test entry outside Lambda package and production bundle. | Never deploy integration server or use its fixed identity mapping outside local tests. |

## Corrections made

1. Date filtering now excludes receipts without a date when only `to` is supplied. A regression test protects the documented behavior.
2. S3 clients use virtual-host regional endpoints. A local boto3 experiment showed the prior default generated `bucket.s3.amazonaws.com`; the new form is `bucket.s3.ap-southeast-2.amazonaws.com`, avoiding redirects during browser POST and matching CSP.
3. New infrastructure covers private/versioned S3, authenticated routes, precise IAM, code-flow Cognito, scheduler trust restrictions and bounded logging. No existing service was replaced.
4. Vite caches are isolated for test/demo/integration processes after a Windows cache collision. This changes local tooling, not authentication or UI behavior.
5. Production bundle checks also reject integration harness markers.

## SNS operational boundary — fail closed

The dedicated topic has no infrastructure-created email subscriptions. `PUT /budget` subscribes only the authenticated user's verified Cognito email, with an exact user filter at creation. The topic resource policy denies publication by other principals and subscription creation outside the API role. Processor/summary roles cannot subscribe, and no application role can mutate subscription filters or topic policy. Do not subscribe an administrator to this financial topic.

**These policies do not neutralise privileged account administrators.** Identity-based grants can permit subscription attribute changes; someone able to replace the topic policy or modify DynamoDB profiles can defeat application assumptions. Before setting `PrivateEmailEnabled=true`, the account owner must restrict `sns:SetSubscriptionAttributes`, subscription creation/deletion, topic policy changes, direct data writes and role assumption to the documented controlled workflow. A university shared account with uncontrollable privileged users is a blocker: keep private email disabled there.

Disable publishing before maintenance, wait for in-flight functions to finish, acquire/observe the application coordination workflow, and wait at least 15 minutes after filter changes. Pending, unknown, unfiltered, mismatched, unreadable or missing subscriptions block **all** financial publication. Audit checks alone cannot prove propagation or prevent an administrator changing a filter immediately afterward. Test initial routing with synthetic expenses in two controlled inboxes before considering real financial data.

Routing failures consume no notification claim and can recover through a later expense/budget check or replay. SNS publication uncertainty is recorded UNKNOWN; crashes may leave CLAIMED. These states are not blindly retried, because SNS may already have accepted the email. Operator review is required; this is not exactly-once delivery. Monthly stable keys suppress repeated application alerts, and weekly keys preserve the original reporting window. Weekly disablement does not remove budget email subscriptions.

## Known risks and limits

- No live Cognito, API Gateway, IAM, S3, Textract, SNS confirmation or email delivery evidence.
- SNS topic server-side encryption is not configured in this minimal template; transport uses TLS. A future customer-managed encryption choice needs appropriate key policy and cost review.
- No independent receipt dead-letter queue/backlog worker is added. Lambda retries twice; exhausted events require operator recovery using the original bucket/key/version. CloudWatch alarms have no email action. Review them during the demo or add a separate operational topic later; never reuse the financial topic.
- Shared-topic audit/lock can block availability when another user is pending; this is the intentional privacy trade-off. Notification history and the 120-month map share a 400 KB budget item and need archival at scale.
- Receipt signature checks are preliminary; real Textract must decode real images. Local fixtures do not establish OCR accuracy. Duplicate detection compares identical file bytes, not different photographs of the same paper.
- Receipt objects and noncurrent versions expire under the 365-day retention policy; DynamoDB expense records remain. Deletion tombstones/hash reservations remain for safety, so deletion is not full personal-data erasure.
- User pool sign-up is enabled for demonstration. Default email quota, abuse, account-wide spending and concurrency must be considered before public promotion. No WAF or per-user receipt quota is included.

## References

[API Gateway JWT validation](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html) explains the issuer/audience and claims boundary. [SNS authorization actions](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sns.html) informs topic-scoped permissions. [SNS filter propagation](https://docs.aws.amazon.com/sns/latest/dg/sns-subscription-filter-policies.html) explains why the application waits and why deployed checks remain necessary. [Scheduler timezone behavior](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html) documents local-time/DST scheduling. [SAM S3 event definition](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-property-function-s3.html) documents event wiring; deterministic bucket names avoid its role/bucket circular dependency.
