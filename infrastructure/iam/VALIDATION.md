# Local IAM proposal validation

The initial 24-test record and sizes below are historical. The subsequent API
action/resource correction passes **33 tests**, with updated policy sizes and
current validation limitations recorded in [API_AUTH_CORRECTION.md](API_AUTH_CORRECTION.md).

Executed 11 October 2026 against the review documents with example account
`296280725059`. No AWS credentials were used, no authenticated AWS API was called,
and no policy/resource was created or changed in AWS. Public AWS documentation and
the public service-authorization reference were consulted.

| Check                                                                                           | Actual observed result                                                                                                                                                                                      |
| ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `python infrastructure/iam/validate.py`                                                         | **12 policy documents passed**, including trust and optional Amplify policy; valid JSON, no duplicate keys, supported action spellings, size limits, explicit regional guards and no wildcard action names. |
| `python -m pytest infrastructure/iam/test_policies.py -q`                                       | **24 passed, 0 failed**, final run 2.41 seconds.                                                                                                                                                            |
| `.venv/Scripts/cfn-lint.exe infrastructure/iam/template.with-boundaries.json -r ap-southeast-2` | **Exit 0**, no findings.                                                                                                                                                                                    |
| Offline SAM transform inside pytest                                                             | **44 resources**, no nested stacks; four boundary references preserved. Botocore HTTP transport patched to reject network access.                                                                           |
| Candidate/source comparison inside pytest                                                       | Only four boundary properties, Cognito Deployment tag, ProjectName allowed value and relative CodeUri differ. Existing YAML preserved.                                                                      |
| IAM Access Analyzer / IAM policy simulation                                                     | **Not run**: would require AWS access and separate authorisation.                                                                                                                                           |
| Real SAM create/update/delete/rollback                                                          | **Not run**: prohibited by this request.                                                                                                                                                                    |

One initial command attempted `python -m cfnlint`; that package does not have a
`__main__` entry point. The command was corrected to the installed `cfn-lint.exe`
entry point and passed. This was a tooling invocation error, not a template finding.
Earlier 22- and 23-test runs passed before the additional Lambda principal and
existing-role boundary restrictions; the final result is the 24-test run above.

## Policy sizes

IAM excludes insignificant whitespace when measuring policy size. These values
are measured from compact JSON; every permissions policy is below 6,144 characters,
and the trust policy is below the default 2,048-character trust limit.

| File                                   | Compact characters |
| -------------------------------------- | -----------------: |
| boundary-ApiRole.json                  |              1,762 |
| boundary-ProcessorRole.json            |              1,422 |
| boundary-SchedulerRole.json            |                254 |
| boundary-SummaryRole.json              |              1,210 |
| cloudformation-api-auth-policy.json    |              1,795 |
| cloudformation-compute-policy.json     |              4,344 |
| cloudformation-iam-policy.json         |              2,958 |
| cloudformation-storage-policy.json     |              2,497 |
| cloudformation-trust-policy.json       |                138 |
| deployment-user-policy.json            |              2,968 |
| optional-amplify-deployer-policy.json  |                867 |
| temporary-first-deployment-policy.json |              2,324 |

Regenerate/revalidate sizes when actual API/pool/app IDs are substituted. Their
lengths can differ from the examples.

## What the regression tests protect

- Boundary-to-role mapping, conditional CreateRole/PutRolePermissionsBoundary and
  explicit refusal to remove a boundary; inline policy and trust changes require
  the boundary to be attached even for a pre-existing role with a matching prefix.
- No execution-role self-management, user administration, managed-policy attachment
  or policy-version creation by the deployment path.
- PassRole target service and resource restrictions for the deployer and runtime roles.
- Exact execution-role parameter for changeset creation, deletion and recovery,
  without incorrectly requiring that parameter on ExecuteChangeSet.
- Exact generated API/pool IDs in steady-state policies, Cognito bootstrap tag
  conditions, and optional Amplify app/branch isolation.
- No direct financial data-plane, SNS publish/subscribe or Textract invocation in
  execution permissions; per-role runtime boundary differences.
- Lambda invocation grants restricted to API Gateway and S3 service principals.
- Account-ID validation, non-Sydney pool rejection, duplicate JSON-key rejection,
  candidate/source equivalence and offline SAM resource expansion.

These are structural regression tests. They are **not an IAM authorisation engine**,
nor a substitute for account-specific Access Analyzer review and an authorised
deployment test. Review the remaining uncertainties and temporary scope in
[README.md](README.md) before any attachment.

## 12 October 2026 — boundaries merged into the source template

`infrastructure/template.yaml` now sets `PermissionsBoundary` on all four explicit
runtime roles, using `ExpenseTracker-Boundary{ApiRole,ProcessorRole,SummaryRole,SchedulerRole}`
(the names of the administrator-owned policies). `prepare.py`, `cloudformation-iam-policy.json`
and `template.with-boundaries.json` use the same names, so the execution policy's
`iam:PermissionsBoundary` conditions match. Local checks only; nothing was deployed.

| Check | Result |
|---|---|
| `sam validate --lint` (SAM CLI 1.168.0), source and candidate templates | **Both valid** |
| `cfn-lint` on both templates, `-r ap-southeast-2` | **Exit 0**, no findings |
| `python infrastructure/iam/validate.py infrastructure/iam` | **12 policy documents passed** |
| `pytest infrastructure/iam/test_policies.py code/tests/test_infrastructure.py` | **50 passed** |
| `pytest code/tests` (full backend suite) | **156 passed** |
| Offline SAM transform of the source template | **44 resources**, exactly 4 IAM roles, each with its boundary |
| Candidate/source comparison | Boundary ARNs equal after resolving the account; only the Cognito tag, ProjectName allowed value and CodeUri differ |

## 12 October 2026 — artifact bucket HeadBucket fix

`aws s3api head-bucket` returned 403 for `expense-deploy` while `get-bucket-location`
succeeded. HeadBucket is authorized as `s3:ListBucket` and carries no `s3:prefix`, so
`ListArtifactPrefix` (StringLike on `s3:prefix`) cannot match. Added `HeadArtifactBucket`:
`s3:ListBucket` on the exact artifact bucket ARN with only the Sydney RequestedRegion
condition. `ListArtifactPrefix`, object, CloudFormation and PassRole statements unchanged.

| Check | Result |
|---|---|
| `validate.py` on checked-in and `rendered/` policies | **12 and 11 passed** (rendered has no optional Amplify policy) |
| `pytest infrastructure/iam/test_policies.py code/tests/test_infrastructure.py` | **51 passed** |
| `deployment-user-policy.json` compact size | 3,189 of 6,144 characters |

## 12 October 2026 — confirmed CreateUserPool and DeleteSchedule denials

Two denials on the execution role, confirmed in AWS by the user:

1. `cognito-idp:CreateUserPool` on `userpool/*`. `CreateTaggedUserPool` required
   `aws:RequestTag/Deployment`, but `template.yaml` sent no `UserPoolTags`. Replaced
   with `CreateUserPoolInSydney` (Resource `*`; the reference lists no resource type;
   RequestedRegion only). Added `UserPoolTags: {Deployment: ict5205-expenses}` to
   the source template so tag-scoped `ManageInitiallyUnknownUserPool` matches the
   handler's follow-up DescribeUserPool/SetUserPoolMfaConfig/TagResource calls.
2. `scheduler:DeleteSchedule` on `schedule/ict5205-expenses-ScheduleGroup-<id>/*` during
   ScheduleGroup rollback. The ScheduleGroup delete handler lists DeleteSchedule and
   authorizes it group-wide. Added `DeleteSchedulesInApplicationGroup` (DeleteSchedule only,
   `schedule/ict5205-expenses-ScheduleGroup-*/*`, Sydney) to the compute policy.

| Check | Result |
|---|---|
| `validate.py` on checked-in and `rendered/` (account 296280725059) | **12 and 11 passed** |
| `sam validate --lint`, source and rendered candidate | **Both valid** |
| `cfn-lint` on both templates | **Exit 0** |
| `pytest infrastructure/iam/test_policies.py code/tests/test_infrastructure.py` | **53 passed** |
| `pytest code/tests` | **157 passed** |
| Compact sizes: compute / bootstrap | 4,616 / 2,819 of 6,144 |

## 12 October 2026 — EventInvokeConfig and HTTP API tagging denials

Live create ended `ROLLBACK_FAILED`. Roles and functions now create (boundary fix confirmed).
Denials: `lambda:PutFunctionEventInvokeConfig`/`DeleteFunctionEventInvokeConfig` on
`function:<name>:$LATEST` (only the unqualified ARN was granted), and `apigateway:POST`
on the encoded `/tags/...%2Fv2%2Fapis%2F*` ARN. Added `ManageLatestEventInvokeConfigs`
(four EventInvokeConfig actions on the three exact `:$LATEST` ARNs) and the HTTP API tag
statements described in API_AUTH_CORRECTION.md.

| Check | Result |
|---|---|
| `validate.py` checked-in / `rendered/` | **12 / 11 passed** |
| `pytest infrastructure/iam/test_policies.py code/tests/test_infrastructure.py` | **58 passed** |
| Compact sizes: compute / api-auth / bootstrap | 5,199 / 2,784 / 3,134 of 6,144 |
