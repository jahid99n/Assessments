# Stage 5 — Live AWS deployment, verification and completion checklist

Prepared 12 October 2026. Every result below was observed directly in this session
unless marked **PENDING** (needs an action by you or an administrator). Nothing here
is simulated. Commands are reproducible from the project root.

## 1. Deployed stack (verified, read-only)

| Item | Observed value |
|---|---|
| Stack / region | `ict5205-expenses`, ap-southeast-2, status **CREATE_COMPLETE** (created 2026-10-11T20:30:58Z) |
| Service role | `arn:aws:iam::296280725059:role/ExpenseTracker-CloudFormationExecution` |
| Parameters | `ProjectName=smart-expense`, `PrivateEmailEnabled=false`, `FrontendOrigin=https://example.com` (placeholder; see §4) |
| Resources | **44/44 CREATE_COMPLETE**: 3 Lambda functions, 10 Lambda permissions, 2 EventInvokeConfigs, 4 IAM roles, HTTP API + stage, Cognito pool/client/domain/branding, 2 DynamoDB tables, S3 bucket + policy, SNS topic + policy, Scheduler group + schedule, 4 log groups, 3 metric filters, 4 alarms |
| ApiUrl | `https://o8a844v2if.execute-api.ap-southeast-2.amazonaws.com` |
| UserPoolId / UserClientId | `ap-southeast-2_h2MfW91kx` / `7nrvsgdrgpu28jd5ljagrhl6i4` |
| CognitoDomain | `smart-expense-296280725059.auth.ap-southeast-2.amazoncognito.com` |
| Tables / bucket / topic | `ict5205-expenses-Expenses-1X8HXFVR6ZREK`, `ict5205-expenses-Budgets-1MA27HJY9UCTC`, `smart-expense-296280725059-ap-southeast-2-receipts`, `smart-expense-expense-alerts` |
| Runtime boundaries | Deployed template sets `ExpenseTracker-Boundary{Api,Processor,Summary,Scheduler}Role`; IAM's `iam:PermissionsBoundary` condition only permits CreateRole with the exact boundary, and all four roles were created |

Commands: `aws cloudformation describe-stacks` / `list-stack-resources --stack-name ict5205-expenses --region ap-southeast-2 --profile expense-deploy`.

## 2. Live API checks without credentials (verified)

| Request | Result |
|---|---|
| GET/POST `/expenses`; GET/PUT/DELETE `/expenses/{id}`; GET `/stats`; GET/PUT `/budget`; POST `/upload-url` | **401** for all nine routes without a token |
| `/expenses` with a forged bearer token | **401** |
| Unknown route | 404 |
| CORS preflight from `https://example.com` | 204, `Access-Control-Allow-Origin: https://example.com`, methods DELETE/GET/OPTIONS/POST/PUT, headers authorization/content-type, max-age 300 |
| CORS preflight from `https://evil.example` | 204 with **no** `Access-Control-Allow-*` headers (browser blocks) |
| Plain HTTP | Connection refused; HTTPS certificate verified |

## 3. Authenticated end-to-end testing — run 2026-10-11T21:00:06Z: 23/24 PASS

Result file: `report/stage5-live-aws-results.json` (no tokens or email recorded).
Passed against the live stack: Cognito SRP sign-in; 401 for missing and tampered JWTs;
authenticated list 200; invalid input 400; create ×2 (201), detail, update, month
filter; budget spent **65.45**, remaining **34.55**, utilisation **65.45 %**; summaries
off; `/stats`; `/upload-url`; multipart upload to S3 (204); tampered signed
Content-Type rejected by S3 (403); deletion of all three test expenses with 404
afterwards; self-deletion of the temporary user. Cross-user isolation was not run
(needs a second confirmed user); the local suites cover it.

**Failed (real defect found):** the synthetic receipt went through S3 → Lambda →
Textract and was parsed, then rejected with "Only AUD is supported". Textract tags a
bare `$` as `USD`, which would reject most Australian receipts. Fixed in
`receipt_parser.py` (bare `$` + inferred USD → AUD with
`currencySource=assumed_from_dollar_sign`; explicit `USD`/`US$`/other codes still
rejected) with new parser tests (backend 161 passed). **The fix is not yet deployed**;
rerun the receipt check after the approved Lambda code update.

How the test was run:

`code/integration/live_smoke.py` performs the remaining Phase A checks against the live
stack. It needs a mailbox you control (Cognito emails a confirmation code), so it
cannot be run unattended. It never prints or stores passwords, tokens or the email
address; results go to `report/stage5-live-aws-results.json`.

```powershell
.venv\Scripts\python.exe code\integration\live_smoke.py signup
.venv\Scripts\python.exe code\integration\live_smoke.py confirm
.venv\Scripts\python.exe code\integration\live_smoke.py run --receipt code\integration\fixtures\synthetic-receipt.png --delete-user
```

Checks: Cognito SRP sign-in; 401 for missing/tampered JWT; create ×2, invalid input
400, detail, update, month-filtered list; budget for 2026-01 with exact arithmetic
(45.50 + 19.95 = **65.45 spent, 34.55 remaining, 65.45 %**); email/summaries off;
`/stats`; presigned multipart upload of a synthetic receipt (TOTAL $12.34) to S3,
S3 → Lambda → Textract processing to PROCESSED, extracted fields and presigned
imageUrl; tampered signed Content-Type rejected by S3; deletion of every created
expense with 404 afterwards; optional self-deletion of the temporary user. Set
`SMOKE_SECOND_EMAIL` (a second confirmed user) to add the cross-user isolation check.
The budget profile row of a deleted test user remains (there is no budget DELETE route).

## 4. Frontend (local preparation verified; hosting PENDING approval)

Verified locally: ESLint exit 0; Vitest 67/67; production build succeeds with the real
API/Cognito values; `test:build` 4/4 (demo build rejected, dev bypass rejected, no demo
code in bundles, unconfigured build fails closed). Receipt images are links, and
uploads go to `*.s3.ap-southeast-2.amazonaws.com`, both allowed by `customHttp.yml`'s CSP.

Amplify app environment variables (non-secret; the client has no secret):

| Variable | Value |
|---|---|
| `VITE_APP_MODE` | `production` |
| `VITE_API_URL` | `https://o8a844v2if.execute-api.ap-southeast-2.amazonaws.com` |
| `VITE_COGNITO_USER_POOL_ID` | `ap-southeast-2_h2MfW91kx` |
| `VITE_COGNITO_CLIENT_ID` | `7nrvsgdrgpu28jd5ljagrhl6i4` |
| `VITE_COGNITO_DOMAIN` | `smart-expense-296280725059.auth.ap-southeast-2.amazoncognito.com` |
| `VITE_REDIRECT_SIGN_IN` | `https://main.<APP_ID>.amplifyapp.com/auth/callback` |
| `VITE_REDIRECT_SIGN_OUT` | `https://main.<APP_ID>.amplifyapp.com/login` |

Required order (each step needs approval):

1. Administrator updates the live CfnApiAuth policy from `infrastructure/iam/rendered/cloudformation-api-auth-policy.json` (exact IDs `o8a844v2if`, `ap-southeast-2_h2MfW91kx`).
2. Administrator creates the Amplify app + `main` branch in Sydney, applies `amplify.yml`, `customHttp.yml` and `infrastructure/amplify-rewrites.json`, sets the variables above and records `https://main.<APP_ID>.amplifyapp.com`.
3. Stack update with `FrontendOrigin=https://main.<APP_ID>.amplifyapp.com` (changes API CORS, S3 CORS, Cognito callback/logout URLs and Lambda `ALLOWED_ORIGIN`; no replacements expected; review the changeset).
4. Deploy the frontend, then test sign-in, dashboard, expenses, budget and receipts in the browser.
5. Only after steps 3–4 succeed: detach `ExpenseTracker-CfnBootstrap` (§5).

## 5. Security and cleanup

| Item | Status |
|---|---|
| Private SNS email | **Verified disabled**: stack parameter `PrivateEmailEnabled=false` |
| Permanent API/Cognito policy with real IDs | **Prepared**: `rendered/cloudformation-api-auth-policy.json`, no `/apis/*` or `userpool/*`, validator PASS, 3,079/6,144 chars. Live update PENDING (administrator) |
| Bootstrap policy | Still required until the FrontendOrigin update; detach afterwards. A live permission simulation needs `iam:SimulatePrincipalPolicy` (administrator) |
| Deployment identity | `expense-deploy` is denied every service-level read tested (Cognito, CloudWatch Logs, DynamoDB, Lambda, S3 bucket config, SNS, CloudWatch alarms, Cost Explorer, IAM, drift): least privilege confirmed; it also means log review, Cognito config and cost checks need an administrator or a separate read-only role |
| CloudWatch logs review (Phase A8) | PENDING administrator: check `/aws/lambda/smart-expense-*` for ERROR lines after the smoke test |
| Actual cost | PENDING administrator (Billing / Cost Explorer). Planning estimate unchanged: about USD 3–6/month (`AWS_Cost_Estimate.md`); Textract ≈ USD 0.01 per receipt page |

Orphaned resources from failed creates (retained by `DeletionPolicy: Retain`; inventory
only, nothing deleted). Observed in stack events during this session:

| Attempt | Cognito pool | Expenses table | Budgets table |
|---|---|---|---|
| Role CreateRole denial | `ap-southeast-2_I6fLmHDYk` | `ict5205-expenses-Expenses-17AZUBXJD9M9H` | `ict5205-expenses-Budgets-1348ACPZZVYRU` |
| HTTP API stage tag denial | `ap-southeast-2_04TauUq0N` | `ict5205-expenses-Expenses-17W1MT8U7I3N5` | `ict5205-expenses-Budgets-7Z0SSBS4MNJ3` |

Events of the other failed attempts were not inspected; `expense-deploy` cannot list
pools/tables. Administrator: in Sydney, list Cognito pools named `smart-expense-users`
and DynamoDB tables prefixed `ict5205-expenses-`; keep only `ap-southeast-2_h2MfW91kx`,
`…Expenses-1X8HXFVR6ZREK` and `…Budgets-1MA27HJY9UCTC`. Orphans are empty and on-demand,
so their cost is near zero, but they should be removed.

## 6. IAM gaps found during deployment (for the reflection section)

Each was a real CloudFormation denial, diagnosed from stack events and fixed with the
narrowest statement; the offline validator and tests were extended each time.

| Denial | Root cause | Fix |
|---|---|---|
| `cognito-idp:CreateUserPool` | Required request tag not sent by the template | Sydney-only create; tag added to template; management stays tag-scoped |
| `scheduler:DeleteSchedule` (rollback) | Group delete authorises `schedule/<group>/*` | DeleteSchedule on application groups only |
| `iam:CreateRole` | Live policy boundary names differed from the real boundary policies | Policy aligned with `ExpenseTracker-Boundary*` |
| `lambda:Put/DeleteFunctionEventInvokeConfig` | Qualified `:$LATEST` ARN does not match unqualified grant | Four actions on the three exact `:$LATEST` ARNs |
| `apigateway:POST` on `/tags/…/v2/apis/*` | SAM tag-on-create | Tag resource limited to encoded V2 API ARNs |
| `apigateway:TagResource` on `/apis/{id}/stages` | Stage tag-on-create uses a named action missing from the saved reference | TagResource/UntagResource on stages only |
| HeadBucket 403 (deployer) | `s3:prefix` condition never present on HeadBucket | Unconditioned ListBucket on the artifact bucket only |

## 7. Assignment requirements (brief and rubric) vs evidence

| Requirement | Status |
|---|---|
| Distributed model (separate processing/storage + another pattern) | Met: API Lambda, event-driven S3→Lambda receipt processor, scheduled weekly Lambda; DynamoDB/S3 storage; SNS publish–subscribe; REST + Textract integration |
| AWS services (rubric: at least 8) | Deployed and verified in the stack: Lambda, API Gateway, DynamoDB, S3, Cognito, SNS, EventBridge Scheduler, CloudWatch (logs, metric filters, alarms), IAM, CloudFormation/SAM. Textract is exercised by the pending smoke test; Amplify by the pending hosting step |
| Cloud storage and datastore | S3 (versioned, private, TLS-only) and DynamoDB (on-demand, encrypted) |
| Client visualisation, deployed on AWS | React dashboard built and tested locally; **Amplify hosting PENDING** |
| Report sections a–j, images folder, IEEE references | Material exists (design docs, Stage 2–5 reports, `images/architecture.*`). Final report document, related work, user manual and references: PENDING (authoring) |
| Signed contribution agreement, video, slides (≤10), readme.txt, `deploy/` folder, source-code printout | PENDING: needs group members' names/signatures and recordings; not created to avoid fabricating details |

## 8. Completion checklist

Verified: stack CREATE_COMPLETE (44 resources); runtime boundaries; all routes 401
unauthenticated; CORS restricted; HTTPS only; private email disabled; least-privilege
deployer; permanent policy rendered with real IDs; frontend lint/unit/build/build-checks;
automated suites on 12 October 2026 — backend pytest 157 passed, IAM policy tests 42
passed, policy validator 12/12, cfn-lint and `sam validate --lint` clean, ESLint clean,
Vitest 67 passed, build checks 4/4, Playwright browser/accessibility 11 passed,
full-stack integration 6 passed, `npm audit --omit=dev` 0 vulnerabilities.

Outstanding (in order): run `live_smoke.py`; administrator updates CfnApiAuth; create
Amplify app; approve FrontendOrigin stack update; deploy frontend and browser-test;
review CloudWatch logs; detach CfnBootstrap; remove orphans; check billing; write the
final report, user manual, slides, video, readme.txt and contribution agreement.
