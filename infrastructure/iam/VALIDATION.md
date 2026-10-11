# Local IAM proposal validation

Executed 11 October 2026 against the review documents with example account
`111122223333`. No AWS credentials were used, no authenticated AWS API was called,
and no policy/resource was created or changed in AWS. Public AWS documentation and
the public service-authorization reference were consulted.

| Check | Actual observed result |
|---|---|
| `python infrastructure/iam/validate.py` | **12 policy documents passed**, including trust and optional Amplify policy; valid JSON, no duplicate keys, supported action spellings, size limits, explicit regional guards and no wildcard action names. |
| `python -m pytest infrastructure/iam/test_policies.py -q` | **24 passed, 0 failed**, final run 2.41 seconds. |
| `.venv/Scripts/cfn-lint.exe infrastructure/iam/template.with-boundaries.json -r ap-southeast-2` | **Exit 0**, no findings. |
| Offline SAM transform inside pytest | **44 resources**, no nested stacks; four boundary references preserved. Botocore HTTP transport patched to reject network access. |
| Candidate/source comparison inside pytest | Only four boundary properties, Cognito Deployment tag, ProjectName allowed value and relative CodeUri differ. Existing YAML preserved. |
| IAM Access Analyzer / IAM policy simulation | **Not run**: would require AWS access and separate authorisation. |
| Real SAM create/update/delete/rollback | **Not run**: prohibited by this request. |

One initial command attempted `python -m cfnlint`; that package does not have a
`__main__` entry point. The command was corrected to the installed `cfn-lint.exe`
entry point and passed. This was a tooling invocation error, not a template finding.
Earlier 22- and 23-test runs passed before the additional Lambda principal and
existing-role boundary restrictions; the final result is the 24-test run above.

## Policy sizes

IAM excludes insignificant whitespace when measuring policy size. These values
are measured from compact JSON; every permissions policy is below 6,144 characters,
and the trust policy is below the default 2,048-character trust limit.

| File | Compact characters |
|---|---:|
| boundary-ApiRole.json | 1,762 |
| boundary-ProcessorRole.json | 1,422 |
| boundary-SchedulerRole.json | 254 |
| boundary-SummaryRole.json | 1,210 |
| cloudformation-api-auth-policy.json | 1,795 |
| cloudformation-compute-policy.json | 4,344 |
| cloudformation-iam-policy.json | 2,958 |
| cloudformation-storage-policy.json | 2,497 |
| cloudformation-trust-policy.json | 138 |
| deployment-user-policy.json | 2,968 |
| optional-amplify-deployer-policy.json | 867 |
| temporary-first-deployment-policy.json | 2,324 |

Regenerate/revalidate sizes when actual API/pool/app IDs are substituted. Their
lengths can differ from the examples.

## What the regression tests protect

* Boundary-to-role mapping, conditional CreateRole/PutRolePermissionsBoundary and
  explicit refusal to remove a boundary; inline policy and trust changes require
  the boundary to be attached even for a pre-existing role with a matching prefix.
* No execution-role self-management, user administration, managed-policy attachment
  or policy-version creation by the deployment path.
* PassRole target service and resource restrictions for the deployer and runtime roles.
* Exact execution-role parameter for changeset creation, deletion and recovery,
  without incorrectly requiring that parameter on ExecuteChangeSet.
* Exact generated API/pool IDs in steady-state policies, Cognito bootstrap tag
  conditions, and optional Amplify app/branch isolation.
* No direct financial data-plane, SNS publish/subscribe or Textract invocation in
  execution permissions; per-role runtime boundary differences.
* Lambda invocation grants restricted to API Gateway and S3 service principals.
* Account-ID validation, non-Sydney pool rejection, duplicate JSON-key rejection,
  candidate/source equivalence and offline SAM resource expansion.

These are structural regression tests. They are **not an IAM authorisation engine**,
nor a substitute for account-specific Access Analyzer review and an authorised
deployment test. Review the remaining uncertainties and temporary scope in
[README.md](README.md) before any attachment.
