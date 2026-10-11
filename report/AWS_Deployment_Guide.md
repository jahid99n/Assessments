# AWS deployment guide — prepared, NOT executed

Stage 4 ends with local verification. **Do not run the cloud-creating commands below until live deployment is explicitly approved.** No `sam deploy`, CloudFormation deployment, Amplify creation, live OCR or email test was executed in Stage 4. Use synthetic receipts/users for the first deployed verification.

**IAM preparation update:** When using `expense-deploy` and the dedicated execution
role, follow [the IAM preparation guide](../infrastructure/iam/README.md). Its bounded
template, explicit artifact bucket/role commands and administrator bootstrap steps
supersede the generic guided-deployment and deletion commands below. The deployment
user is not authorised for all administrator verification commands in this guide.

## 1. Account and workstation prerequisites

Use an authorised university/personal AWS account with MFA on its root user and no routine root usage. Prefer IAM Identity Center/SSO temporary credentials. Ensure the account owner permits Cognito, Lambda, API Gateway HTTP API, DynamoDB, S3, Textract AnalyzeExpense, SNS, EventBridge Scheduler, CloudWatch and Amplify in Sydney. Check account service quotas, email quotas, IAM role/PassRole permissions and account restrictions first. Create a USD 10 billing alert; alerts do not stop spending. Keep financial SNS delivery disabled until the separate privacy gate below passes.

Install Node 22.13+ (tested Node 24.13), uv/Python 3.12, AWS CLI v2 and AWS SAM CLI from their official installers. Install/start Docker Desktop's Linux container engine for reproducible Lambda builds. See [AWS CLI installation](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html), [SAM CLI installation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html) and [container builds](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-using-build.html).

Observed locally: AWS CLI and SAM CLI were absent; Docker CLI existed but its Linux daemon was unavailable. `cfn-lint` and the `aws-sam-translator` library were installed in the project development environment. The source template, offline SAM expansion and expanded CloudFormation lint passed. A SAM CLI/container build has **not** been tested.

## 2. Run the offline checks first

From the project root in PowerShell:

```powershell
uv python install 3.12
uv sync --frozen
uv run --frozen pytest -q --junitxml=report/stage4-backend.xml
uv run --frozen cfn-lint infrastructure/template.yaml --region ap-southeast-2
uv run --frozen python infrastructure/validate_local.py
uv run --frozen cfn-lint report/stage4-expanded-template.json --region ap-southeast-2
Set-Location code/frontend
npm.cmd ci
npm.cmd test
npm.cmd run lint
npm.cmd run test:browser
npm.cmd run test:integration
npm.cmd run build
npm.cmd run test:build
Set-Location ../..
```

Run these sequentially for predictable CPU use. Edge must be installed for browser tests. Integration tests start/stop localhost ports 5180/5181 and execute real frontend/backend code with moto and mocked Textract. Port 5173 is used by demo browser tests, 5174 by the build verifier. The build verifier expects no real frontend AWS configuration. Never include `code/integration` or `code/frontend/integration` in a deployment package.

## 3. Configure approved AWS authentication and region

**Future authorised deployment only:**

```powershell
aws configure sso --profile ict5205
aws sso login --profile ict5205
$env:AWS_PROFILE = 'ict5205'
$env:AWS_DEFAULT_REGION = 'ap-southeast-2'
aws sts get-caller-identity
aws --version
sam --version
docker version
```

Confirm the account returned by STS before continuing. Never copy secret keys into this repository, frontend variables or reports. The template contains a Sydney-only rule. Use a unique project name matching its parameter pattern; it controls deterministic bucket/function/domain naming and must be unique for this stack/account. Do not deploy two stacks with the same ProjectName in one account/region.

## 4. Reserve the frontend origin

The backend intentionally permits one exact HTTPS frontend origin. Create an empty Amplify **static WEB** app and `main` branch first to obtain that origin. This is the first cloud-creating step and requires deployment approval. It does not require a GitHub push or repository connection:

```powershell
$app = aws amplify create-app --name smart-expense --platform WEB --custom-rules file://infrastructure/amplify-rewrites.json --custom-headers file://customHttp.yml --region ap-southeast-2 | ConvertFrom-Json
$appId = $app.app.appId
aws amplify create-branch --app-id $appId --branch-name main --region ap-southeast-2
$frontendOrigin = 'https://main.' + $app.app.defaultDomain
```

Keep these non-secret resource identifiers for later steps. Console alternative: Amplify → create app → deploy without Git → static app, then configure the same rewrite and headers. Do not enable SSR, WAF, custom domains or unrelated Amplify backend services for this demonstration.

## 5. Validate and build the backend package

From project root, with Docker running:

```powershell
uv export --frozen --no-dev --no-emit-project --format requirements-txt --output-file code/backend/requirements.txt
sam validate --lint --template-file infrastructure/template.yaml --region ap-southeast-2
sam build --use-container --template-file infrastructure/template.yaml
```

`requirements.txt` is already exported from the lockfile and contains runtime dependencies only, with hashes. SAM's CodeUri includes only `code/backend`, not tests or the Windows virtual environment. Verify the built Lambda packages contain the three handler modules and dependencies. Inspect `.aws-sam/build/template.yaml`. Do not substitute the Windows `.venv` as a Lambda package.

## 6. Deploy infrastructure — only after approval

Read `Security_Review.md`, choose a project name and confirm the origin is exact. Leave private email false:

```powershell
sam deploy --guided --template-file .aws-sam/build/template.yaml --stack-name ict5205-expenses --region ap-southeast-2 --capabilities CAPABILITY_IAM --parameter-overrides "ProjectName=smart-expense" "FrontendOrigin=$frontendOrigin" "PrivateEmailEnabled=false"
```

Review the change set before allowing execution in the guided flow. Confirm only expected resources. Save configuration locally if desired; `samconfig.toml` and `.aws-sam` are ignored. The stack creates two on-demand tables, private/versioned S3, Cognito user pool/public client/managed login branding, HTTP API, three Python 3.12 functions, scoped roles, SNS topic, a Monday scheduler and logs/alarms. It creates no email subscriptions automatically.

```powershell
$stack = aws cloudformation describe-stacks --stack-name ict5205-expenses --region ap-southeast-2 | ConvertFrom-Json
$outputs = @{}
$stack.Stacks[0].Outputs | ForEach-Object { $outputs[$_.OutputKey] = $_.OutputValue }
$outputs
```

## 7. Verify storage and function configuration

```powershell
aws dynamodb describe-table --table-name $outputs.ExpensesTable --region ap-southeast-2
aws dynamodb describe-table --table-name $outputs.BudgetsTable --region ap-southeast-2
aws s3api get-bucket-versioning --bucket $outputs.ReceiptBucket
aws s3api get-public-access-block --bucket $outputs.ReceiptBucket
aws s3api get-bucket-encryption --bucket $outputs.ReceiptBucket
aws s3api get-bucket-cors --bucket $outputs.ReceiptBucket
aws s3api get-bucket-notification-configuration --bucket $outputs.ReceiptBucket
aws lambda get-function-configuration --function-name smart-expense-receipt-processor --region ap-southeast-2
```

Expected: Expenses partition `userId`, sort `expenseId`; Budgets partition `userId`; PAY_PER_REQUEST; bucket versioning Enabled, all four public blocks true, AES256 encryption, actual frontend origin, receipt-prefix ObjectCreated Lambda event. Runtime python3.12; processor timeout 60 seconds (below 90-second lease); API timeout 29 seconds; PRIVATE_EMAIL_ENABLED=false. Resource names in commands assume the sample ProjectName.

Receipts expire after 365 days; noncurrent versions also expire after 365 days. This is a retention policy, not permanent archival. Pending abandoned objects receive the same retention because no separate pending-object tagging worker was introduced. Abort incomplete multipart uploads after one day. Tables/bucket/user pool use Retain for deletion/replacement; take responsibility for eventual cleanup.

## 8. Verify API and Cognito before uploading real data

An unauthenticated GET to `$outputs.ApiUrl/expenses` must return 401, never expense data. Inspect API Gateway's JWT issuer and audience, every route's authorizer and CORS. Do not add an unauthenticated proxy/default route or Lambda function URL. Cognito's app client must be public/no secret, authorization code only, scopes openid/email/profile, callback `$frontendOrigin/auth/callback` and sign-out `$frontendOrigin/login`. Managed login uses Essentials and default branding created by the template; no manual password form is needed.

Create two controlled test accounts through the deployed sign-up screen and confirm both emails. Cognito's default sending service is suitable only within its small daily quota. Validate wrong/expired tokens, wrong audience/issuer and missing token with synthetic requests. ID tokens are the agreed contract. API Gateway's JWT authorizer does not inherently distinguish ID versus access tokens; both identity and intended client validation must be reviewed. End users receive no AWS IAM permissions to invoke Lambda or access DynamoDB directly.

## 9. Configure and publish React

Copy `code/frontend/.env.example` to its ignored `.env.local`. Set production mode, API URL, pool/client/domain from outputs, callback and sign-out to the exact Amplify origin. These VITE values are public configuration, not credentials. Never set VITE_APP_MODE=demo for deployment.

Build locally:

```powershell
Set-Location code/frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run build
Set-Location ../..
```

For manual static hosting, zip the **contents** of dist, not its parent directory:

```powershell
$artifactPath = Join-Path $env:TEMP 'ict5205-expense-frontend.zip'
Compress-Archive -Path code/frontend/dist/* -DestinationPath $artifactPath -Force
$deployment = aws amplify create-deployment --app-id $appId --branch-name main --region ap-southeast-2 | ConvertFrom-Json
Invoke-WebRequest -Uri $deployment.zipUploadUrl -Method Put -InFile $artifactPath -ContentType 'application/zip'
aws amplify start-deployment --app-id $appId --branch-name main --job-id $deployment.jobId --region ap-southeast-2
```

Do not print/store the presigned deployment upload URL in reports. Verify the branch URL, deep links `/expenses` and `/auth/callback`, SPA rewrites and security response headers. `customHttp.yml` is applied by app configuration, not assumed to work merely because it exists. CSP currently allows required Sydney service hosts; tighten it to exact API/bucket/domain hosts after outputs are known. Receipt links open in a new tab with no referrer; signed URLs are bearer permissions and must not be shared/logged.

If repository-connected hosting is later explicitly authorised, root `amplify.yml` supplies the monorepo appRoot/build/output settings. Configure `AMPLIFY_MONOREPO_APP_ROOT=code/frontend`, Node 24, public VITE variables and headers in Amplify. No Git connection or push is required by the manual path above.

## 10. SNS confirmation and private-email gate

Keep PrivateEmailEnabled=false initially. Through each test account's Budget page, subscribe using that account's verified email and enable weekly summaries if desired. Click each SNS confirmation email. Expect `pending_or_blocked` while private email is disabled, while a subscriber is pending, or during the 15-minute propagation hold.

Before enabling delivery, the account owner must verify that only the application can create subscriptions/publish and that no uncontrolled principal can change filters, topic policy, budget profiles or roles. Topic policy restricts publish and subscribe, but privileged administrators remain outside the application's lock. Never add an unfiltered admin email to this topic. If the account cannot guarantee this isolation, **leave publishing disabled**.

After all subscriptions confirm and at least 15 minutes have passed since the last change, audit each subscription's exact user filter, MessageAttributes scope, email and stored ARN. Only in the approved deployment session, update the parameter to true through SAM and test with **synthetic** financial values for two controlled users. Verify each inbox receives only its own alert/summary. A third pending/unsafe subscriber must block both users' private sends. Revert false immediately if anything is uncertain. Local tests are not authority to enable private email.

## 11. Scheduler and logs

```powershell
aws scheduler get-schedule --name $outputs.WeeklyScheduleName --group-name $outputs.WeeklyScheduleGroup --region ap-southeast-2
aws logs tail /aws/lambda/smart-expense-expense-api --since 1h --region ap-southeast-2
aws logs tail /aws/lambda/smart-expense-receipt-processor --since 1h --region ap-southeast-2
aws logs tail /aws/lambda/smart-expense-weekly-summary --since 1h --region ap-southeast-2
```

Expected schedule: `cron(0 9 ? * MON *)`, Australia/Sydney, flexible window OFF, input preserves `<aws.scheduler.scheduled-time>`. AWS handles daylight saving; do not encode a fixed UTC offset. Weekly aggregation uses preceding Monday–Sunday local dates. Verify Scheduler's invocation role and the original scheduled-time input on retries.

Inspect the four CloudWatch alarms and 14-day log groups. The shared notification-failure metric also catches logged API failures because a handled 500 may not increment Lambda Errors. Alarms have **no outbound actions** in this minimal template; monitor them in Console. If email operations alerts are later needed, approve a separate operational SNS topic. Do not subscribe operations staff to the financial topic.

## 12. Live acceptance checklist

Record actual results only after deployment: sign-up/login/logout; two-user separation; all nine routes; manual 0.10+0.20 totals; edit across months/delete; paginated filters; budgets; real JPEG/PNG upload; rejected invalid/oversized/mutated/expired uploads; private S3 access denied anonymously; Australian date parsing; duplicate event/file protection; transient retry; dashboard reflects receipt completion; correct two-inbox notifications; Monday Sydney weekly summary; logs/alarms. Compare OCR against the actual receipt manually. Do not reuse synthetic fixtures as OCR accuracy evidence.

## 13. Recovery, rollback and cleanup

For failed infrastructure creation, inspect stack Events. Fix the error and rerun validation/build; do not repeatedly create unrelated replacement stacks. Keep the previous source and successful frontend ZIP so a frontend release can be rolled back by republishing it. Review CloudFormation replacement changes carefully; retained tables/user pools are not automatically migrated. Take on-demand backups if preserving real data (additional costs).

For receipt retries exhausted after two Lambda retries, find the original expense's bucket/key/**version** in controlled operator tooling. Fix the cause, wait for a stale 90-second lease to expire, then replay the original S3 event to the processor. Do not generate a new expense ID or blindly clear hash reservations. No durable dead-letter queue is provisioned, so keep enough operator evidence to reconstruct the versioned event. For notifications, review UNKNOWN/CLAIMED before any retry; clearing claims may duplicate email.

For complete cleanup, first disable the weekly schedule and private publication, sign users out/stop frontend access, then remove the Amplify app and delete the CloudFormation stack using the approved account. Example commands for a later, explicitly authorised cleanup:

```powershell
aws amplify delete-app --app-id $appId --region ap-southeast-2
sam delete --stack-name ict5205-expenses --region ap-southeast-2
```

**Retained resources remain:** inventory the exact bucket, both tables and user pool from the saved outputs before deleting anything. Export needed evidence/data securely. Empty every S3 object version and delete marker in that exact bucket (ordinary `aws s3 rm --recursive` is insufficient for versioned storage), then delete that bucket. Delete the two retained tables and retained Cognito pool only after confirming their identities and data-retention decision. Remove confirmed SNS subscriptions if any remain, and remove only this project's SAM deployment artifacts; never empty a shared SAM-managed bucket indiscriminately. Review retained/replaced resources and Cost Explorer afterward. No cleanup command was run in Stage 4.
