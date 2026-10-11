# Stage 4 implementation addendum

11 October 2026. Local implementation/preparation only; no AWS deployment.

The ten-service architecture, three Python 3.12 Lambdas, two tables, private receipts,
nine HTTP routes and fail-closed SNS design remain unchanged. No queue, extra database,
server or alternative email service was introduced. Original Phase 0/1 documents and
diagrams remain historical design evidence; the Stage 2 addendum remains applicable.

## Corrections based on inspection/testing

- `GET /expenses?to=...` now excludes records without a date, consistent with the
  existing date-filter contract. All other request/response fields remain unchanged.
- S3 presigned POST and GET use Sydney virtual-host endpoints rather than boto3's
  global default. This avoids redirect/CORS issues and matches hosting CSP.
- Stage 3's report incorrectly listed receipt download URLs as missing. The existing
  backend detail route already supplies five-minute `imageUrl` and the frontend has
  Open receipt image. No new download endpoint was needed. The older report is retained;
  this correction and the frontend README supersede that claim.
- Local Vite modes and the integration harness now have separate caches to avoid
  concurrent Windows rename/module identity errors. Cold chart compilation is warmed
  in component-test setup, while real browser tests still exercise lazy loading.

## Deployment choices made concrete

- `infrastructure/template.yaml` defines a regional HTTP API with default JWT
  authorizer, Cognito public code-flow client/managed login branding, three functions,
  two on-demand tables, versioned encrypted private S3, dedicated SNS, Sydney Scheduler,
  scoped IAM and CloudWatch logs/alarms. Template defaults keep private email disabled.
- Cognito uses Essentials for managed login version 2; default email sending is intended
  only for a small demonstration and has account/service quotas.
- Deterministic bucket names use project/account/region to avoid SAM's S3 event circular
  dependency. Changing ProjectName can replace resources; review change sets carefully.
- Offline SAM expansion revealed its automatic S3 permission allowed any bucket in
  the account. The final template declares the same S3 event in CloudFormation and
  restricts invocation to both the exact bucket ARN and account; no processing flow changes.
- API timeout is 29 seconds, processor/summary 60 seconds; processing and notification
  leases remain 90/120 seconds. Lambda async retry settings allow two retries and an
  event age of six hours. Recovery after exhaustion is still an operator responsibility.
- Logs retain 14 days. Four alarms and one shared custom failure metric are prepared;
  no alarm email actions are attached. An operational topic would require separate
  approval; never add an administrator to the financial SNS topic.
- S3 current/noncurrent receipt versions expire after 365 days; multipart leftovers
  after one day. This cost-control policy also applies to abandoned uploaded objects.
  DynamoDB records can outlive image retention. Tables, bucket and user pool are retained
  on stack deletion/replacement, so cleanup must explicitly account for them.
- Amplify remains a static WEB app. Root build/header configuration and SPA rewrites
  are prepared; hosting creation and application of these settings are not yet tested.

## Local evidence boundary

The test-only HTTP gateway maps fixed synthetic identities to API Gateway claims. It
does not validate JWT cryptography. Browser multipart requests pass through the actual
upload helper into an S3 policy simulator, moto versioned storage, the real receipt
processor, mocked Textract, moto DynamoDB and the real frontend. Fixtures are labelled
synthetic; no image decoding/OCR accuracy or email delivery evidence is implied.

CloudFormation lint and structural IAM assertions cannot prove account-level authority,
service quotas, email confirmation/filter propagation, exact deployed CORS or runtime
behavior. See the Stage 4 report and deployment/security guides for approval gates.
