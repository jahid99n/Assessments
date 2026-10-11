# Proposed deployment IAM — review only

Prepared 11 October 2026. **Nothing in this directory has been applied to AWS.**
The checked-in policies use AWS's example account `111122223333`, API ID
`REVIEW_API_ID`, user pool `ap-southeast-2_REVIEW`, and Amplify app `reviewapp`.
They are syntactically valid review examples, **not policies to attach unchanged**.
Generate account-specific copies before an administrator reviews and attaches them.
Account IDs are not credentials; this generator never reads credentials or calls AWS.

## Recommended arrangement

```text
expense-deploy -> ExpenseTracker-Deployers
                  deployment-user-policy
                         |
                         | CloudFormation changeset + restricted iam:PassRole
                         v
              ExpenseTracker-CloudFormationExecution
                  4 permanent execution policies
                  1 temporary first-deployment policy
                         |
                         v
              ict5205-expenses in ap-southeast-2
                  4 runtime roles, each with an administrator-owned boundary
```

Keep the execution role, its policies, the four boundary policies and the artifact
bucket outside the application stack. An existing administrator provisions these
once. Neither `expense-deploy` nor the execution role can change those policies,
administer users/groups, create access keys, or change the execution role's trust.
The deployment user can upload application code, execute changesets and delete this
stack, so this is still a privileged application-maintainer identity. Code changes
can access application data through runtime roles; IAM deployment separation does
not make the deployer untrusted or prevent malicious application code.

CloudFormation retains its execution-role association. Anyone granted operations
on this stack may use the associated role even without a new `PassRole` check.
Limit other identities' stack access too. The supplied policy requires the exact
execution-role ARN on changeset creation, deletion and rollback recovery. Executing
an existing changeset is restricted by **stack ARN**, which is the IAM resource for
that action; `RoleArn` is not an ExecuteChangeSet parameter.
[AWS service-role guidance](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/using-iam-servicerole.html).

## Inspection and resource coverage

Reviewed the complete `../template.yaml`, `../validate_local.py`, the offline SAM
expansion in `../../report/stage4-expanded-template.json`,
`../../report/AWS_Deployment_Guide.md`, `../../amplify.yml`,
`../../customHttp.yml` and `../amplify-rewrites.json`. No `samconfig` file or nested
stack was found. SAM expands the application to **44 resources**:

| Resources | Execution permissions and scope |
|---|---|
| 3 Lambda functions, 10 invoke permissions, 2 async invoke configurations | Create/read/update/delete functions and configurations; tag functions; add/remove invoke permissions on the three exact function ARNs. New invocation grants only to API Gateway and S3. No direct InvokeFunction permission for deployment identities. |
| 4 IAM runtime roles | Create only `ict5205-expenses-{ApiRole,ProcessorRole,SummaryRole,SchedulerRole}-*`, each with its corresponding boundary; manage inline policies/trust/tags; delete roles; pass only Lambda roles to Lambda and the scheduler role to Scheduler. |
| 2 DynamoDB tables | Lifecycle, describe and tag operations on `ict5205-expenses-Expenses-*` and `ict5205-expenses-Budgets-*`; no expense read/write/query/scan permission for deployment identities. |
| S3 bucket and bucket policy | Create/configure exact `smart-expense-ACCOUNT-ap-southeast-2-receipts`, including CORS, notifications, lifecycle, versioning, encryption, ownership, public-access block and TLS bucket policy; no receipt object access. |
| Cognito pool, client, domain, managed-login branding | Pool configuration, client/domain/branding lifecycle, MFA configuration reads/writes and tags. Exact pool ARN after bootstrap. No administrative user-data APIs. |
| SNS topic and topic policy | Lifecycle, attributes/policy and tags on `smart-expense-expense-alerts`; no publishing, subscribing or subscription changes by deployment identities. Runtime roles retain their existing SNS permissions. |
| HTTP API and default stage | API Gateway GET/POST/PUT/PATCH/DELETE on the exact API and children after bootstrap; includes integrations, JWT authorizer, routes, stage and tags created from SAM's OpenAPI definition. |
| Scheduler group and weekly schedule | Group/schedule lifecycle and tags on stack-generated name prefixes; only the application scheduler role can be passed. |
| 4 log groups, 3 metric filters, 4 alarms | Lifecycle, retention, filters and tags on exact Lambda log groups and stack-generated API log/alarm names; separate regional account-level log-delivery operations. No log-content reading granted. |

The user policy additionally covers CloudFormation validation, changeset creation,
inspection/execution/deletion, stack status/events/resources/template reads, update
cancellation, rollback recovery and stack deletion. The AWS-managed SAM transform
has its own CreateChangeSet permission. Packaging permits read/upload/delete and
multipart cleanup **only within the artifact bucket's `ict5205-expenses/` prefix**.
Artifact listing requires that prefix. No `s3:ListAllMyBuckets` or receipt content
access is granted. SAM packaging may read object version/tag metadata.
[SAM transform permission](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/control-access-with-iam.html),
[SAM uploader implementation](https://github.com/aws/aws-sam-cli/blob/develop/samcli/lib/package/s3_uploader.py).

The template contains no EC2, VPC, ECR, RDS, KMS key, SES identity, custom resource,
CloudFormation registry extension, Lambda layer, or nested stack. Corresponding
administration permissions are deliberately absent. SSE-S3 artifacts avoid KMS
artifact permissions. DynamoDB uses the template's service-managed encryption
configuration; changing to customer-managed KMS requires a separate review.

Amplify is **outside SAM**, and its app/branch must be provisioned by an administrator.
The optional Amplify policy permits manual ZIP deployments to the existing `main`
branch and job inspection only. It does not create apps/branches, connect GitHub,
change app environment settings/rewrites/headers, or manage build service roles.
Administrator setup must apply the existing hosting configuration. No GitHub token
or repository integration permission is needed for the documented manual ZIP path.

## Files and attachment destinations

All entries below are customer-managed permissions policies except the trust policy.
Use these names exactly because the boundary and role ARNs are referenced in JSON.

| File | AWS policy/role name | Attach where |
|---|---|---|
| `deployment-user-policy.json` | `ExpenseTracker-Deploy` | `ExpenseTracker-Deployers` group only |
| `cloudformation-storage-policy.json` | `ExpenseTracker-CfnStorage` | Execution role |
| `cloudformation-compute-policy.json` | `ExpenseTracker-CfnCompute` | Execution role |
| `cloudformation-api-auth-policy.json` | `ExpenseTracker-CfnApiAuth` | Execution role |
| `cloudformation-iam-policy.json` | `ExpenseTracker-CfnIam` | Execution role |
| `temporary-first-deployment-policy.json` | `ExpenseTracker-CfnBootstrap` | Execution role temporarily, never the user/group |
| `boundary-ApiRole.json` | `ExpenseTracker-ApiRole-Boundary` | Permissions boundary on ApiRole, applied by candidate template |
| `boundary-ProcessorRole.json` | `ExpenseTracker-ProcessorRole-Boundary` | Permissions boundary on ProcessorRole |
| `boundary-SummaryRole.json` | `ExpenseTracker-SummaryRole-Boundary` | Permissions boundary on SummaryRole |
| `boundary-SchedulerRole.json` | `ExpenseTracker-SchedulerRole-Boundary` | Permissions boundary on SchedulerRole |
| `cloudformation-trust-policy.json` | Trust for `ExpenseTracker-CloudFormationExecution` | Role's trust relationship, not a permissions policy |
| `optional-amplify-deployer-policy.json` | `ExpenseTracker-DeployAmplify` | Group only if frontend deployment is authorised and actual app ID rendered |

The execution permissions are split into four policies to stay under the **6,144
non-whitespace-character limit per managed policy**. Four permanent plus one
temporary attachment fit the default role attachment quota. A boundary limits a
runtime role's inline permissions; it does not grant permissions by itself. The
boundary files mirror the current runtime policy actions, with Sydney conditions
and stack-generated table ARN patterns. They are not execution-role boundaries.
[IAM quotas](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html),
[permissions boundaries](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_boundaries.html).

## Required proposed template adjustments

**The existing `infrastructure/template.yaml` is unchanged.**
`template.with-boundaries.json` is a separate SAM candidate, using CloudFormation's
equivalent JSON syntax. It adds only:

1. The respective administrator-owned `PermissionsBoundary` ARN to each existing role.
2. `UserPoolTags: {Deployment: ict5205-expenses}` for bootstrap Cognito isolation.
3. `AllowedValues: [smart-expense]` for ProjectName, matching these policies.
4. An adjusted relative CodeUri so the separate template still builds existing code.

No resources, route contracts or runtime role names/paths change. There are still
44 transformed resources and the existing retain policies remain. IAM role names
remain CloudFormation-generated, so `CAPABILITY_IAM` remains sufficient.
Do not deploy the original unbounded template using these policies: CreateRole
will intentionally be denied. Review the candidate or merge these four changes
into the original before a separately authorised deployment. Regenerate policies
and boundaries whenever runtime permissions or resource names change.

Role creation requires the exact `iam:PermissionsBoundary` condition. Setting a
boundary is allowed only to that same policy. Removing a boundary is explicitly
denied. Runtime inline policies and trust can be updated only on the four role
prefixes **when the respective boundary is already attached**; this also prevents
using an older unbounded role with a matching name as an escalation route.
For an already-deployed stack whose roles lack boundaries, an administrator must
attach the matching boundary to each existing runtime role before migration;
otherwise IAM-policy/trust updates intentionally fail closed. Confirm the existing
stack/project names match the fixed `ict5205-expenses` / `smart-expense` scope first.
Managed-policy attachment and policy-version creation are not granted.
The execution-role trust names only `cloudformation.amazonaws.com`; it does not
trust the deployment user. This uses the documented standard stack-service-role
trust rather than assuming registry-extension SourceArn conditions work here.
[CloudFormation least-privilege service roles](https://docs.aws.amazon.com/prescriptive-guidance/latest/least-privilege-cloudformation/service-roles-for-cloudformation.html).

## Bootstrap, steady-state operation, and deletion

An administrator needs temporary setup authority for IAM CreatePolicy/GetPolicy,
CreateRole/UpdateAssumeRolePolicy, AttachRolePolicy, AttachGroupPolicy and
AddUserToGroup, plus policy-version management for later tightening. These are
**administrator responsibilities**, not additional grants to `expense-deploy`.
They also need S3 CreateBucket and configuration rights for the artifact bucket,
and optional Amplify CreateApp/CreateBranch/UpdateApp/UpdateBranch for hosting setup.
Do not temporarily attach AdministratorAccess, IAMFullAccess or PowerUserAccess to
the deployment user. Do not let the application stack own its own boundary policies.

The temporary execution policy covers:

* HTTP API creation at the `/apis` collection and initially unknown API IDs.
  **During bootstrap it can modify/delete any HTTP API in this account's Sydney
  region.** API Gateway ARNs omit the account field. This is the main temporary
  overbreadth; run in a dedicated assessment account where practical, limit the
  attachment to the approved deployment window, and detach immediately afterward.
* User-pool creation, requiring the Deployment request tag, and management of
  Sydney pools carrying that same resource tag. Avoid using this reserved tag on
  unrelated pools. Pool tags are present in the candidate's create request.
* Creation of only `AWSServiceRoleForAPIGateway`, with the exact
  `iam:AWSServiceName = ops.apigateway.amazonaws.com` restriction. If an administrator
  has already provisioned this account-wide role, this grant need not be used.
  Do not delete this shared service-linked role during application cleanup.
  [API Gateway service-linked role](https://docs.aws.amazon.com/apigateway/latest/developerguide/using-service-linked-roles.html).

After first success, record ApiUrl's API ID and UserPoolId from **this stack's
outputs**, regenerate with them, replace the `ExpenseTracker-CfnApiAuth` policy's
default version, then detach `ExpenseTracker-CfnBootstrap`. Ordinary code updates,
configuration updates, changesets, and stack deletion use the permanent policies.
Creating a replacement API/user pool or recreating the whole deleted stack needs
a newly reviewed bootstrap window. Keep the old exact IDs authorised until
replacement/rollback completes, then narrow to the new IDs. When creating a new
managed-policy version, remove an older **non-default** version if the five-version
limit has been reached; never delete the currently used policy.

Deleting the stack retains Expenses, Budgets, Receipts and Users as specified by
the template. It deletes the API, client/domain/branding, functions, runtime roles,
SNS topic, schedule and monitoring resources. Retain is not an IAM security boundary:
the execution role has resource lifecycle delete permissions for rollback/replacement,
and a reviewed template change could change Retain. Artifact bucket, execution role,
boundaries, and Amplify app are outside this stack and survive deletion. An
administrator must separately review removal of retained data, all S3 versions and
bootstrap resources. The deployment user cannot empty receipts or purge artifact
versions. IAM's DeleteRole requires inline policies to be removed; a permissions
boundary is not listed as a prerequisite to remove. If the live resource handler
nevertheless requests boundary removal, investigate the deletion path with an
administrator; do not weaken the permanent boundary-removal deny.
[DeleteRole requirements](https://docs.aws.amazon.com/IAM/latest/APIReference/API_DeleteRole.html).

## Regional limits and unavoidable wider permissions

Every non-IAM Allow has `aws:RequestedRegion = ap-southeast-2`; resource ARNs also
contain Sydney wherever the service supports it. Bucket creation additionally
requires `s3:LocationConstraint = ap-southeast-2`. Use regional SDK/CLI endpoints.
The template's Sydney rule remains, but IAM provides independent restrictions.

| Exception | Why and remaining restriction |
|---|---|
| IAM roles, policies, trust, PassRole and service-linked role bootstrap | IAM is account-global, with no regional ARN component. Applying a Sydney RequestedRegion condition to IAM would break global endpoint calls. Exact role/policy names, application role prefixes, boundaries and service conditions provide the restriction. |
| S3 bucket/object ARNs | ARNs contain neither region nor account; exact account-bearing bucket names, artifact prefix and request-region conditions are used. Bucket location is separately constrained on creation. |
| ValidateTemplate and GetTemplateSummary | Inline/local templates have no existing stack ARN; Resource `*`, Sydney only. This reveals template structure, not account-wide data permissions. |
| Cognito CreateUserPool | No resource-level ARN before creation; Resource `*`, Sydney and Deployment request tag, temporary only. |
| Cognito DescribeUserPoolDomain | Does not support resource-level scoping; Resource `*`, Sydney only. Reads domain metadata, not users. |
| Logs delivery APIs, PutResourcePolicy, DescribeResourcePolicies, DescribeLogGroups | Account-level APIs without resource-level scope; Resource `*`, Sydney only. PutResourcePolicy is powerful and could alter regional service-delivery policies; retain it only for the documented HTTP API logging workflow and review changesets. |
| Textract AnalyzeExpense | Runtime processor boundary only, not deployment identities; API has no receipt ARN scope. Resource `*`, Sydney only. |
| Amplify/Cognito managed hosting distribution | Application control APIs are regional, but service-managed edge hosting can be global. No direct CloudFront permissions are granted. |

Do not describe Resource `*` as automatically global: many of these actions remain
region-restricted. These policies are additive allows; unrelated future policy
attachments or resource policies can widen effective access. Permission boundaries
are not a universal sandbox against all resource-policy grants. SCPs, permission
boundaries on the deployment/execution identities, endpoint policies and explicit
denies can also reduce the proposed access. Account administrators must inspect
effective permissions before attachment.
[HTTP API logging permissions](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-logging.html),
[AWS service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/reference_policies_actions-resources-contextkeys.html).

## Exact future Console setup steps — administrator only

These are instructions for later approval; **do not perform them merely to review
these files**. The user with zero permissions cannot bootstrap itself.

1. Sign in with an existing administrator or delegated IAM administrator, verify the
   account ID from the account menu, and use MFA. Select **Asia Pacific (Sydney)**
   for regional services. IAM remains global. Confirm `expense-deploy` belongs to
   this account. Do not create access keys as part of this setup.
2. Locally render the JSON with the account ID using the command below. For the first
   deployment leave the two generated resource IDs at their REVIEW defaults; their
   steady-state statements match no real resources until you supply actual IDs.
   Review both the policies and the candidate template. Do not use the example account.
3. Open **IAM → Policies → Create policy → JSON**. Paste one rendered permissions
   file at a time, choose **Next**, enter its exact name from the attachment table,
   review IAM policy validation findings, and choose **Create policy**. Create the
   four boundary policies, four execution policies, deployment policy and temporary
   bootstrap policy. Do not create a managed policy from the trust JSON or template.
   Errors must be resolved; do not blindly dismiss warnings about wildcard scope.
4. Open **IAM → Roles → Create role → Custom trust policy**. Paste the rendered
   `cloudformation-trust-policy.json`. Choose **Next** and select exactly the four
   `ExpenseTracker-CfnStorage`, `-CfnCompute`, `-CfnApiAuth`, and `-CfnIam` policies.
   Do not set one of the runtime boundary policies as this role's boundary. Choose
   **Next**, name the role **ExpenseTracker-CloudFormationExecution**, verify the
   trust and permissions, and create it. Leave the default `/` role path. Record
   its ARN. A delegated administrator's own boundary may prohibit these steps and
   requires that administrator's organisation to approve them.
5. When the first deployment window is approved, open this role → **Permissions →
   Add permissions → Attach policies**, select **ExpenseTracker-CfnBootstrap**, and
   attach it. Attach it only here. If the role already exists, inspect its trust
   and all attachments first; do not reuse an unrelated more-powerful role.
6. Open **IAM → User groups → ExpenseTracker-Deployers → Permissions → Add
   permissions → Attach policies**. Select only **ExpenseTracker-Deploy** and
   attach it. Under the group's **Users → Add users**, select **expense-deploy**
   and add it if not already a member. Under **IAM → Users → expense-deploy →
   Permissions**, verify the inherited group policy and absence of unrelated direct
   policies/groups. Boundary policies and execution policies do not belong here.
   Set up/enforce MFA under your account's normal sign-in policy; these files do
   not provision login profiles, passwords or access keys.
7. Administrator: **S3 → Create bucket**, general-purpose bucket, Sydney, name
   `smart-expense-ACCOUNT-ap-southeast-2-artifacts`. Keep ACLs disabled (Bucket owner
   enforced) and all Block Public Access settings enabled. Enable versioning,
   select SSE-S3 default encryption and create the bucket. No public/read grants
   are needed: the same-account identity policies grant artifact access. Configure
   a lifecycle rule to abort incomplete multipart uploads after one day and expire
   noncurrent artifact versions after an agreed rollback retention period. Keep
   current artifacts needed by active stacks; do not choose automatic deletion of
   current deployment artifacts. This bucket is separate from private receipts.
8. If hosting is needed, an administrator reserves the Amplify app and `main` branch
   in Sydney, applies the repository's hosting settings, and records its exact HTTPS
   origin. Render with its actual app ID, create **ExpenseTracker-DeployAmplify**,
   and attach only that optional policy to the group if manual frontend publishing
   is authorised. No optional policy is needed for backend-only SAM deployment.
9. After a separately approved first deployment, go to **CloudFormation → Sydney →
   ict5205-expenses → Outputs**. Record ApiUrl's first hostname segment and
   UserPoolId. Regenerate locally with those IDs. Go to **IAM → Policies →
   ExpenseTracker-CfnApiAuth → Edit → JSON**, replace with the regenerated exact-ID
   policy, review and save as the default version. Then go to execution role →
   **Permissions**, select **ExpenseTracker-CfnBootstrap → Remove** and confirm
   detachment. Check IAM role boundaries on the four stack-created roles. Record
   the role/policy versions and perform a separately approved update smoke test.

Console labels can differ slightly between IAM interface versions. Do not grant
extra list/admin permissions to the deployer merely to make every Console screen
work: the baseline is intended for SAM/CLI operations on a named stack. Console
stack-list views may require ListStacks, which is deliberately not granted.

## Local commands and future deployment commands

Run from the project root. These first commands are entirely local:

```powershell
# Install the existing Python 3.12 development environment if needed:
uv sync --python 3.12 --group dev

# Replace this placeholder with the administrator-verified account ID.
$deploymentAccount = '<12-digit-account-id>'
.venv/Scripts/python.exe infrastructure/iam/prepare.py --account-id $deploymentAccount --output infrastructure/iam/rendered
.venv/Scripts/python.exe infrastructure/iam/validate.py infrastructure/iam/rendered
.venv/Scripts/python.exe -m pytest infrastructure/iam/test_policies.py -q
.venv/Scripts/cfn-lint.exe infrastructure/iam/rendered/template.with-boundaries.json -r ap-southeast-2

# After first deployment, regenerate and review before changing the managed policy:
.venv/Scripts/python.exe infrastructure/iam/prepare.py --account-id $deploymentAccount --api-id '<actual-api-id>' --user-pool-id '<actual-Sydney-pool-id>' --output infrastructure/iam/rendered
# Add --amplify-app-id '<actual-app-id>' only for optional existing-app publishing.
```

Rendering overwrites only generated files in the chosen output folder. Use the
ignored `rendered/` folder for account-specific copies. Omitted optional flags do
not delete old files: if an optional Amplify file remains from an earlier rendering,
do not attach it without checking its app ID and current authorisation.

**The following contact AWS or require deployment approval; none were executed.**
Use already-approved local authentication. Do not place credentials in commands or
files. These commands supersede the guide's generic `sam deploy --guided` example:

```powershell
$executionRoleArn = "arn:aws:iam::${deploymentAccount}:role/ExpenseTracker-CloudFormationExecution"
$artifactBucketName = "smart-expense-${deploymentAccount}-ap-southeast-2-artifacts"
$frontendOrigin = 'https://<actual-amplify-host>'

sam validate --lint --template-file infrastructure/iam/rendered/template.with-boundaries.json --region ap-southeast-2
sam build --template-file infrastructure/iam/rendered/template.with-boundaries.json --use-container
sam deploy --template-file .aws-sam/build/template.yaml --stack-name ict5205-expenses --region ap-southeast-2 --s3-bucket $artifactBucketName --s3-prefix ict5205-expenses --role-arn $executionRoleArn --capabilities CAPABILITY_IAM --parameter-overrides "ProjectName=smart-expense" "FrontendOrigin=$frontendOrigin" "PrivateEmailEnabled=false" --no-execute-changeset
# Review the generated changeset before executing it; use its returned name/ARN.
aws cloudformation execute-change-set --stack-name ict5205-expenses --change-set-name '<reviewed-changeset>' --region ap-southeast-2

# Explicit service role on deletion/recovery is required by the deployer policy:
aws cloudformation delete-stack --stack-name ict5205-expenses --role-arn $executionRoleArn --region ap-southeast-2
aws cloudformation wait stack-delete-complete --stack-name ict5205-expenses --region ap-southeast-2
# Only if an update is actually stuck in UPDATE_ROLLBACK_FAILED:
aws cloudformation continue-update-rollback --stack-name ict5205-expenses --role-arn $executionRoleArn --region ap-southeast-2
```

Do not use `--resolve-s3` or SAM's auto-created managed artifact stack; neither is
authorised. Do not use `sam delete` with this baseline: versions that omit RoleARN
will be denied. Use the explicit CloudFormation delete command above, preserving
artifacts until rollback/retention review. Local build/lint needs no AWS deployment
permissions; remote ValidateTemplate uses the regional validation permission.
No custom KMS artifact key, image repository or CloudFormation upload bucket is
authorised. `--no-execute-changeset` still uploads artifacts and creates a changeset;
it is not a purely local dry run.

## Validation evidence and remaining uncertainty

See [VALIDATION.md](VALIDATION.md) for executed checks. Public AWS authorization
reference data was read without account authentication and the used-action subset
is saved in `action-reference.json`. This verifies action spelling/resource support
metadata; it does not prove that a service supplies every condition context key
on every CloudFormation handler path.

Still requires a separately approved AWS review: IAM Access Analyzer findings on
rendered policies; effective IAM/SCP/boundary/resource-policy evaluation; actual
create/update/delete/rollback handler calls and resource-name formats; API Gateway
encoded tag ARN handling; Cognito resource-tag evaluation/propagation during create;
service-linked role creation; CloudWatch delivery policy behaviour; role deletion
with the boundary-removal deny; artifact access using the selected SAM CLI version;
regional service availability and account quotas. This proposal is not a claim of
successful deployment or mathematically minimal effective permissions.

When an actual denial occurs, record the exact action, resource, handler and
CloudTrail request, then review the smallest correction. Do not replace these
policies with service-wide wildcards. Keep `PrivateEmailEnabled=false` until the
existing SNS subscription-isolation acceptance checks pass in AWS.
