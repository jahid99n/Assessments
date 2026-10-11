# Stage 4 integration testing and deployment readiness

Completed locally on 11 October 2026 (Asia/Dhaka). **No AWS deployment, live Textract call, private email publication, GitHub push or final academic report was performed.** Public AWS documentation/pricing was consulted without account credentials. The original service architecture and UI were preserved.

Final Git inspection found branch `main` and uncommitted implementation changes. No commit, branch switch or push was performed. Default frontend report filenames now use generic names so future runs do not overwrite Stage 3 evidence. Stage 4 evidence is saved separately; the historical Stage 3 browser XML was restored from its committed 11-pass baseline after the existing test reporter rewrote it.

## Final observed results

**236 automated tests passed; 0 failed; 0 skipped.** These counts describe the final successful runs, not all development attempts. Machine evidence was parsed to produce [stage4-test-summary.json](stage4-test-summary.json).

| Suite | Expected behavior / purpose | Actual final result | Evidence |
|---|---|---|---|
| Python backend + infrastructure assertions | All existing backend behavior, two regression fixes, 13 structural security checks | 152 passed; 0 failed; 76.12 seconds | [JUnit](stage4-backend.xml) |
| Frontend Vitest/RTL | API client, validation, auth adapter, CRUD/budgets/uploads, errors and demo separation | 67 passed; 0 failed; 36.32 seconds | [JUnit](stage4-frontend.xml) |
| Edge browser + accessibility | Six interaction/responsive tests and five Axe scans | 11 passed; 0 failed; 38.8 seconds | [JUnit](stage4-browser.xml) |
| Local full-stack integration | Real React/API adapter → HTTP gateway → real Python handlers → simulated AWS → real UI | 6 passed; 0 failed; 37.9 seconds | [JUnit](stage4-integration.xml) |

The Python count comprises the original 137 backend cases, two new application regression cases and 13 infrastructure assertions. Test durations are local suite observations, **not performance benchmarks**.

Additional executed checks:

- `npm run lint`: exit 0.
- `npm run build`: exit 0. Final emitted JavaScript: main 299.97 kB, dashboard 378.28 kB, Cognito 78.48 kB; CSS 23.23 kB, uncompressed Vite sizes.
- `npm run test:build`: four checks passed, zero failed. Reject demo production build; reject development NODE_ENV bypass; exclude demo and integration markers from production JavaScript; missing AWS configuration fails closed in actual Edge without AWS requests. [Evidence](stage4-build-checks.json).
- `cfn-lint` on source SAM and expanded CloudFormation: exit 0, no findings. [Evidence](stage4-cfn-lint.json).
- Offline `aws-sam-translator` expansion: succeeded, 44 generated/retained resources. No AWS transport permitted. [Permission summary](stage4-sam-expansion.json), [expanded template](stage4-expanded-template.json). **Expanded output uses a fictional code artifact and must never be deployed.**
- `uv pip check`: 48 installed packages compatible after validation tooling was added. `compileall` for backend/local harness: exit 0.
- `npm audit`: zero reported vulnerabilities. [Evidence](stage4-npm-audit.json). This is a dependency database result, not proof of application security; no equivalent Python vulnerability database audit is claimed.
- Targeted source/document scans found no AWS access-key-shaped literals or private-key blocks in the scanned project paths. Dummy `testing` credentials in local mocks are intentional. This was a pattern scan, not an exhaustive secret-detection product audit.

AWS CLI and SAM CLI were not installed. Docker CLI was present but the Linux engine connection failed. Therefore **SAM CLI validate/build, Linux container packaging and live CloudFormation validation were not executed**. Source lint and offline SAM expansion are useful structural evidence, not substitutes for those steps.

## Full-stack test boundary

The separate local frontend entry uses the real App, pages, runtime provider, API client and upload helper. Fixed synthetic identities replace only the Cognito/API Gateway verification boundary. The Python localhost gateway creates HTTP API-compatible route/claims events and calls the production API handler. It does not manufacture successful expense responses.

Browser FormData passes unchanged through the actual XMLHttpRequest helper; Playwright intercepts the AWS transport and forwards it to a loopback S3-compatible simulator. That simulator checks the actual issued signed fields, policy expiry, exact ownership/type/key constraints, file-last ordering and content size, then writes a versioned object through moto. It invokes the real receipt processor asynchronously. Only Textract output is stubbed; the real parser, categorisation, conditional writes, hash duplicate reservations, DynamoDB queries and financial calculations execute.

Backend botocore HTTP is blocked; browser non-local traffic is blocked, except the intercepted upload which is fulfilled locally. The test-only gateway and entry are outside deployment packages. No real JWT signature, AWS policy cryptography, AWS event delivery, OCR accuracy or inbox delivery is established by these tests.

## Nine API routes exercised together

| Route | Integrated observed result |
|---|---|
| POST `/expenses` | Manual input persisted; numeric 0.10 and 0.20 produced backend total 0.30. Real React form also persisted 12.30. |
| GET `/expenses` | Actual DynamoDB-backed records, date/category filtering and cursor continuation; other user's list empty. |
| GET `/expenses/{id}` | Details and receipt PENDING/FAILED/PROCESSED retrieval; cross-user detail returned 404. |
| PUT `/expenses/{id}` | Real adapter update changed totals from 0.30 to 1.30; UI edit changed 12.30 to 15.30. |
| DELETE `/expenses/{id}` | Deleted records stopped contributing to totals; baseline manual total returned to zero. |
| GET `/stats` | Dashboard consumed real backend totals; receipt completion displayed $40.00; duplicate event/file did not add a second charge. |
| GET `/budget` | Month-specific budget/spending view and historic receipt spending. |
| PUT `/budget` | Limit saved through real adapter/backend, with correct spent/remaining calculation. |
| POST `/upload-url` | Real policy generated and returned; real multipart upload path followed it. |

Unauthenticated local HTTP requests returned 401. A forged userId query returned 400. These prove application contract behavior, **not deployed JWT validation**. Existing backend tests additionally cover all nine routes without trusted claims, cross-user mutation, forged cursors, malformed bodies, transient service errors and sanitised error messages. Existing frontend tests cover surfaced API/upload errors.

## Receipt workflow findings

- JPEG and PNG MIME paths completed with synthetic signature-prefixed fixture bytes and mocked Textract. Australian `04/11/2024` became `2024-11-04`, with historic budget spending 40.00.
- Parsed Coles became Groceries, total 40.00, GST 0.38. Real dashboard totals reflected completed storage records.
- Original S3 event replay and a second upload of identical bytes did not double-charge. Duplicate file failure was visible in the actual receipt UI.
- Missing total produced explicit FAILED and a user-visible amount error. A transient Textract failure produced retryable FAILED, then recovered by replaying the original event and checking status in the UI; the monthly total became 80.00 after the second distinct successful receipt.
- Modified owner metadata and MIME fields were rejected by the local policy simulation. 5,242,881 bytes was rejected; exactly 5,242,880 bytes passed the size policy. Invalid image contents then failed the real processor's signature check. Size-policy acceptance does not mean a valid image was decoded.
- Backend tests separately exercise incorrect stored ownership metadata, missing/invalid object versions, failed DynamoDB writes, expired/competing claims, later overwrites, deletion races and non-resurrection.

## Fixes and implementation additions

1. Fixed `to`-only expense filtering to exclude receipts without extracted dates, matching the API contract.
2. Made S3 upload/download signatures use Sydney regional virtual-host URLs. A local boto3 check established that the previous default produced a global URL.
3. Added the localhost full-stack harness and six browser integration cases; no production auth bypass or alternative business implementation was added.
4. Added SAM/CloudFormation for all required backend services, scoped roles, retry settings, strict CORS, private versioned storage, managed Cognito login and CloudWatch monitoring. The offline SAM transform revealed its automatic S3 permission was account-wide; final explicit CloudFormation permission is restricted to the exact bucket and account.
5. Added static Amplify build/header/rewrite configuration, pinned Lambda runtime requirements, local infrastructure validation tooling, guides and security/cost review.
6. Isolated Vite caches by mode/harness and warmed the real lazy chart module in component-test setup. Browser tests still load the real lazy module.
7. Corrected a Stage 3 documentation error: receipt downloads already exist via the detail response's five-minute `imageUrl` and the frontend Open receipt image action. No new endpoint is necessary. The Stage 3 report is retained as historical evidence; this correction supersedes its missing-download claim.

See [Stage 4 addendum](../Phase4_Integration_Addendum.md) for infrastructure choices, retention and architectural implications.

## Development failures and recovery

The first harness startup failed because Playwright resolved a relative server path from the integration configuration directory. Explicit working directories corrected it. A generated integration JUnit path was also corrected to the root report directory; the actual final XML was preserved there.

An initial concurrent browser run produced **8 passed, 3 failed** after a Windows EPERM rename collision in Vite's shared dependency cache and duplicate React module loading. Isolated mode/integration cache directories resolved it; the final 11-test browser suite passed.

Two frontend verification runs produced **66 passed, 1 failed**: the lazy chart module's cold compilation exceeded the DOM query's default wait. Moving compilation into `beforeAll` preserved all rendering assertions and yielded the final 67 passed. This test setup correction is not a measured application speed improvement.

No assertions were removed to obtain the successful results. No AWS mock was replaced with real network access. Final infrastructure source and expanded lint had no findings; no deployed stack success is claimed.

## Security and SNS readiness

The source/default-authorizer review, 13 infrastructure assertions and original backend isolation tests pass. API credentials and verified email come only from trusted authorizer context. The template exposes no Lambda function URLs. S3 is private, versioned, AES256-encrypted and HTTPS-only; browser origin is exact, not `*`. Runtime IAM grants only required service actions and resources, with Textract's documented resource-scoping limitation.

SNS application routing passes local tests for exact per-user filters, confirmation state, 15-minute propagation hold, full-topic audit, locking, suppression and uncertain publish recovery. Unknown/unfiltered/pending/mismatched/unreadable subscribers cause no publish. UNKNOWN/CLAIMED outcomes require operator review; no exactly-once delivery claim is made.

**PrivateEmailEnabled remains false by default.** Actual SNS confirmation, data-plane filtering and delivery have not been tested. Topic policy restricts publishing/subscribing, but privileged account principals can still undermine isolation through filter/policy/profile changes. An account unable to enforce the controlled workflow must keep private email disabled. See [security review](Security_Review.md).

## Remaining deployment prerequisites

1. Explicit approval for live AWS deployment and the selected account/region.
2. AWS CLI and SAM CLI installation, working Docker Linux engine, SAM lint and container package build.
3. Account quotas/permissions and a unique project name; create the Amplify origin and apply exact Cognito/API/S3 origins and public frontend configuration.
4. Actual managed login, JWT verification/expiry, CORS, S3 event and Textract image-processing acceptance tests.
5. Account-level SNS governance and two confirmed controlled inboxes; test synthetic user-specific delivery before enabling real financial emails.
6. Confirm hosting headers/rewrites, Scheduler/DST behavior, CloudWatch alarms and recovery procedures. No durable receipt failure queue or operational email topic is added.

Student-scale limits remain: user-query aggregation is not a concurrent snapshot, the weekly batch can outgrow a 60-second function, the shared SNS audit can block availability, history needs archival at scale, and no perceptual duplicate detection/refunds/multi-currency/full erasure exists.

Estimated cost is **USD 3–6/month** for five users and 100 receipt pages under the stated workload, approximately $3.80 before optional credits/taxes. This is a planning estimate, not a bill; see [cost assumptions and official sources](AWS_Cost_Estimate.md). Follow the [deployment guide](AWS_Deployment_Guide.md) for exact future steps, verification, rollback and retained-resource cleanup.

**Readiness:** local Stage 4 is complete and suitable for a controlled deployment review. Live deployment readiness is conditional on the prerequisites above; the app is not claimed to be production-verified. Stop here pending explicit deployment approval.
