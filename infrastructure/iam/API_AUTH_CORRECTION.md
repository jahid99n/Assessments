# API Gateway action/resource correction

This correction changes local JSON and its generator only. It does not update an
AWS policy, change attachments, create resources or deploy anything. The existing
AWS customer-managed policy reported by the user is `ExpenseTracker-CfnApiAuthPolicy`.

## Findings and exact changes

The application uses `AWS::Serverless::HttpApi`, transformed to
`AWS::ApiGatewayV2::Api` with an OpenAPI body and a default stage. It does not use a
REST API. Management permissions use the `apigateway:` IAM prefix, not
`apigatewayv2:`. SDK operation names are not necessarily IAM action names.

The old `ManageKnownHttpApi` combined five verbs with both an individual API ARN
and a generic child wildcard. In particular, POST does not apply to the individual
Api resource; it creates resources at collection ARNs. PUT is applicable to Api
for reimport, but not to the application's ordinary route/authorizer/stage objects.
The replacement groups each verb with supported resource types:

| Statement | Actions | Resource suffix after `arn:aws:apigateway:ap-southeast-2::` |
|---|---|---|
| ManageKnownHttpApi | GET, PUT, PATCH, DELETE | `/apis/REVIEW_API_ID` |
| ManageKnownHttpApiCollections | GET, POST | `/apis/REVIEW_API_ID/authorizers`, `/integrations`, `/routes`, `/stages` (each with the full API prefix) |
| ManageKnownHttpApiChildren | GET, PATCH, DELETE | Each of those four collection paths followed by `/*` |

The bootstrap policy uses the same groups with `*` in the API-ID position and
retains a separate `CreateHttpApi` statement with POST/PUT on the exact `/apis`
collection. No new services, administrator access or unrestricted Resource `*`
API Gateway grant was introduced. Child scopes now explicitly describe this
template's resources; unrelated models, exports and other children previously
matched by the broad suffix are not included.

The old `TagKnownHttpApi` and `TagInitiallyUnknownHttpApi` statements are removed.
Their percent-encoded strings were well-formed under the **REST Management Tags**
ARN format. However, the V2 authorization reference does not list that Tags resource
type. Carrying a REST tagging resource into an HTTP API policy is not justified by
the V2 table. HTTP API tag operations and tagging at creation must be authorized
using the supported management verbs and V2 target resource scopes. No fictitious
`apigateway:TagResource`, `apigateway:GetApi`, `apigateway:CreateApi` or
`apigatewayv2:*` action was added. Do not confuse the HTTP request URL
`/v2/tags/{resource-arn}` with an IAM resource ARN.

The corrected action/resource combinations follow the published reference. Actual
CloudFormation tag-on-create and subsequent tag updates still require live
verification; local checks do not establish AWS handler behavior.

## Operations and ARN checks

| Operation | Applicable permission in this proposal |
|---|---|
| CreateApi / ImportApi | Bootstrap POST/PUT on `/apis`; no future API ID needed |
| GetApi / UpdateApi / DeleteApi | GET/PATCH/DELETE on `/apis/{id}` |
| ReimportApi | PUT on `/apis/{id}` plus supported child operations as required by imported routes/integrations/authorizers |
| List/create authorizers, integrations, routes, stages | GET/POST on the corresponding child collection |
| Read/update/delete those objects | GET/PATCH/DELETE on the corresponding individual-resource pattern |
| GetTags / TagResource / UntagResource | Management verbs and the supported V2 resource scopes; no operation-named IAM action or REST `/tags/…` ARN |

The API Gateway management ARN has an intentionally empty account segment (`::`).
It uses `/apis`, not `/restapis`, `/v2/apis`, or the `execute-api` invocation service.
Every Allow keeps `aws:RequestedRegion = ap-southeast-2`.

`REVIEW_API_ID` is intentionally retained as a literal placeholder. It matches no
deployed API and is never interpolated by CloudFormation inside an attached policy.
The actual Cognito placeholder is **`ap-southeast-2_REVIEW`**, not the literal string
`REVIEW_USER_POOL_ID`. All actions in `ManageKnownUserPool` were checked against the
current public Cognito reference and support the userpool ARN. DescribeUserPoolDomain
has no resource-level support, so its separate Sydney-restricted Resource `*`
statement is unchanged. Pool creation remains in bootstrap with its request-tag
condition. None of the Cognito permissions or account identifiers was changed.

## Local results

* `python -m pytest infrastructure/iam/test_policies.py -q`: **33 passed, 0 failed**
  in 2.72 seconds. Includes offline SAM expansion, placeholder preservation, Cognito
  scope checks, all generated API action/resource pairs and rejection of the old
  POST-on-Api pairing, PUT-on-Stage, REST tag paths and invented IAM action names.
* The checked-in **12** policy documents pass the local validator inside pytest;
  the **11** rendered policy documents also pass `validate.py` directly. The optional
  Amplify policy exists only in the checked-in example set in this run.
* `cfn-lint` on `infrastructure/template.yaml`, the checked-in candidate and the
  rendered candidate: **exit 0**, no findings. SAM templates remain unchanged.
* The API/auth policy measures **2,347** compact characters; temporary bootstrap
  measures **2,864**, both below the 6,144-character managed-policy limit.
* AWS CLI is installed. An Access Analyzer ValidatePolicy attempt could not load
  the configured login session. No Access Analyzer result was obtained and no login
  or credential changes were performed. Do not interpret local PASS as an AWS
  Access Analyzer or deployment PASS.

`apigateway-v2-reference.json` records the resource/action subset used by the new
pair checks. Its data comes from AWS's public programmatic reference and was checked
against the separate V2 table. The programmatic reference combines both API Gateway
management versions, so the validator deliberately restricts itself to this project's
HTTP resource types. It is not a general IAM evaluator.

## Expected IAM summary behavior

Warnings attributable to the removed REST `/tags/…` resource in the HTTP policy and
the mixed individual/collection action assignments should be eliminated by these
changes. This is an expectation, not a claim that the Console was retested.
Both service summaries share the `apigateway` prefix: a remaining REST-only summary
can still report V2 resources as inapplicable. Do not broaden permissions merely
to make both summary rows green. Inspect statement-level validation findings and
the V2 reference before making another change.

Intentional restrictions remain: placeholders authorize no existing API/pool;
permanent policy cannot create another API; all regional operations are Sydney-only;
bootstrap access is needed for first creation and resource replacement. Bootstrap
can manage other APIs in the account's Sydney region while attached. Remove it
promptly after exact IDs are installed. This correction does not make that temporary
wildcard application-isolated.

## Safe update of the existing customer-managed policy

These are manual instructions, not actions performed by this review.

1. Use an authorised administrator/delegated policy administrator session, preferably
   temporary credentials with MFA. Confirm the intended AWS account.
2. Open **IAM → Policies → ExpenseTracker-CfnApiAuthPolicy**. Check the policy ARN
   and **Entities attached**; confirm it is the intended CloudFormation execution
   policy, not a deployment-user policy. Updating the default version affects all
   identities already attached to it; no detach/reattach is required.
3. Save a copy of the current default version for rollback. Choose **Edit → JSON**.
   Replace the complete document with
   `infrastructure/iam/rendered/cloudformation-api-auth-policy.json`.
   Preserve `REVIEW_API_ID` and `ap-southeast-2_REVIEW` before deployment.
4. Inspect the editor's policy validation findings. Resolve errors; if the broad
   service summary still warns, inspect its exact statement/action/resource details.
   Do not substitute a wildcard or administrator policy to silence it.
5. Choose **Next/Review → Save changes**, making the corrected version the default.
   If the five-version limit is reached, remove an older **non-default** version
   first. Retain the previous default as a rollback version where possible.
6. The bootstrap JSON was corrected too. If an existing bootstrap managed policy
   has already been created, review/update its JSON similarly using
   `rendered/temporary-first-deployment-policy.json`. This is an update instruction,
   not authorisation to attach it or deploy now.
7. After a separately authorised deployment, obtain API ID from `ApiUrl` and pool
   ID from `UserPoolId`, regenerate with `--api-id` and `--user-pool-id`, validate,
   then update the permanent policy's default version. Only after that succeeds,
   remove bootstrap access according to the existing administrator procedure.

Local commands (from the project root):

```powershell
.venv/Scripts/python.exe infrastructure/iam/validate.py infrastructure/iam/rendered
.venv/Scripts/python.exe -m pytest infrastructure/iam/test_policies.py -q
.venv/Scripts/cfn-lint.exe infrastructure/template.yaml infrastructure/iam/template.with-boundaries.json infrastructure/iam/rendered/template.with-boundaries.json -r ap-southeast-2
```

Optional read-only AWS validation after authorised authentication is available:

```powershell
aws accessanalyzer validate-policy --policy-document file://infrastructure/iam/rendered/cloudformation-api-auth-policy.json --policy-type IDENTITY_POLICY --region ap-southeast-2 --no-cli-pager
aws accessanalyzer validate-policy --policy-document file://infrastructure/iam/rendered/temporary-first-deployment-policy.json --policy-type IDENTITY_POLICY --region ap-southeast-2 --no-cli-pager
```

This requires `access-analyzer:ValidatePolicy`; it does not attach a policy or
require creation of an analyzer. Do not grant the deployment user policy-management
rights just to run validation.

## Official references

* [API Gateway Management V2 authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_apigatewayv2.html)
* [API Gateway Management authorization](https://docs.aws.amazon.com/service-authorization/latest/reference/list_apigateway.html)
* [API Gateway public programmatic reference](https://servicereference.us-east-1.amazonaws.com/v1/apigateway/apigateway.json)
* [HTTP API tagging endpoint](https://docs.aws.amazon.com/apigatewayv2/latest/api-reference/tags-resource-arn.html)
* [Cognito public authorization reference](https://servicereference.us-east-1.amazonaws.com/v1/cognito-idp/cognito-idp.json)
* [Access Analyzer ValidatePolicy](https://docs.aws.amazon.com/access-analyzer/latest/APIReference/API_ValidatePolicy.html)

## 12 October 2026 — tagging ARN reinstated after a live denial

A live CloudFormation create was denied `apigateway:POST` on
`arn:aws:apigateway:ap-southeast-2::/tags/arn%3Aaws%3Aapigateway%3Aap-southeast-2%3A%3A%2Fv2%2Fapis%2F*`
while creating the SAM HttpApi (SAM adds the `httpapi:createdBy` tag on create).
This overrides the removal above: HTTP API tagging *is* authorized on the `/tags/`
resource wrapping the URL-encoded `/v2/apis` ARN. New statements grant only
GET/POST/DELETE (GetTags/TagResource/UntagResource):

- Bootstrap `ManageInitiallyUnknownHttpApiTags`: encoded `.../v2/apis/*` (matches the literal `*` used before the ID exists).
- Steady state `ManageKnownHttpApiTags`: encoded `.../v2/apis/<id>` and `.../v2/apis/<id>/*` (stage).

`apigateway-v2-reference.json` gained a `Tags` type limited to encoded V2 API ARNs;
REST `/restapis` or unencoded tag ARNs and PUT remain rejected by the validator.
