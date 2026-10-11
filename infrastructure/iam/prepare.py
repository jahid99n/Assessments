"""Generate reviewable IAM documents locally. This script never calls AWS.

The checked-in JSON uses AWS's example account 296280725059, NOT a real account.
Run with your account ID into a separate directory before administrator review.
"""
import argparse
import copy
import json
import os
import re
from pathlib import Path

from cfnlint.decode import decode

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REGION = "ap-southeast-2"
STACK = "ict5205-expenses"
PROJECT = "smart-expense"
ROLES = ("ApiRole", "ProcessorRole", "SummaryRole", "SchedulerRole")


def statement(sid, actions, resources, *, regional=True, condition=None):
    result = {"Sid": sid, "Effect": "Allow", "Action": actions, "Resource": resources}
    conditions = {"StringEquals": {"aws:RequestedRegion": REGION}} if regional else {}
    for operator, values in (condition or {}).items():
        conditions.setdefault(operator, {}).update(values)
    if conditions:
        result["Condition"] = conditions
    return result


def policy(*statements):
    return {"Version": "2012-10-17", "Statement": list(statements)}


def http_api_permissions(api_id, prefix):
    """V2 management resource types; REST /tags ARNs do not belong here.

    An individual Api supports GET/PUT/PATCH/DELETE. Creation is POST on
    collections. The application's authorizers, integrations, routes and stages
    support GET/PATCH/DELETE individually, and GET/POST on their collections.
    Tagging uses the management verbs on the V2 target resource (including
    tag-on-create); do not invent apigateway:TagResource or apigatewayv2 actions.
    """
    api = f"arn:aws:apigateway:{REGION}::/apis/{api_id}"
    collections = [f"{api}/{kind}" for kind in ("authorizers", "integrations", "routes", "stages")]
    # Tagging (including SAM's tag-on-create, confirmed by a live CloudFormation denial)
    # is authorized on /tags/<URL-encoded V2 ARN>; during creation the ID is a literal *.
    # GET/POST/DELETE are GetTags/TagResource/UntagResource. The ARN is case-sensitive.
    encoded_api = f"arn%3Aaws%3Aapigateway%3A{REGION}%3A%3A%2Fv2%2Fapis%2F{api_id}"
    tag_targets = [encoded_api] if api_id == "*" else [encoded_api, f"{encoded_api}%2F*"]
    return [
        statement(f"{prefix}HttpApi", ["apigateway:GET", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], api),
        statement(f"{prefix}HttpApiCollections", ["apigateway:GET", "apigateway:POST"], collections),
        statement(f"{prefix}HttpApiChildren", ["apigateway:GET", "apigateway:PATCH", "apigateway:DELETE"],
                  [f"{resource}/*" for resource in collections]),
        statement(f"{prefix}HttpApiTags", ["apigateway:GET", "apigateway:POST", "apigateway:DELETE"],
                  [f"arn:aws:apigateway:{REGION}::/tags/{target}" for target in tag_targets]),
        # The ApiGatewayV2 Stage handler checks apigateway:TagResource on the stages
        # collection when tagging on create (confirmed by a live denial); Untag on update.
        statement(f"{prefix}HttpApiStageTags", ["apigateway:TagResource", "apigateway:UntagResource"],
                  [f"{api}/stages", f"{api}/stages/*"]),
    ]


def generate(account, api_id="REVIEW_API_ID", pool_id="ap-southeast-2_REVIEW", amplify_id=None):
    if not re.fullmatch(r"\d{12}", account):
        raise ValueError("Account ID must have exactly 12 digits")
    if not re.fullmatch(r"[A-Za-z0-9_]+", api_id):
        raise ValueError("Invalid API ID")
    if not re.fullmatch(r"ap-southeast-2_[A-Za-z0-9]+", pool_id):
        raise ValueError("User pool must be in Sydney")
    if amplify_id and not re.fullmatch(r"[a-z0-9]+", amplify_id):
        raise ValueError("Invalid Amplify app ID")
    arn = lambda service, resource: f"arn:aws:{service}:{REGION}:{account}:{resource}"
    iam = lambda resource: f"arn:aws:iam::{account}:{resource}"
    role_arns = {name: iam(f"role/{STACK}-{name}-*") for name in ROLES}
    boundary = {name: iam(f"policy/ExpenseTracker-Boundary{name}") for name in ROLES}
    execution = iam("role/ExpenseTracker-CloudFormationExecution")
    stack = arn("cloudformation", f"stack/{STACK}/*")
    artifact_name = f"{PROJECT}-{account}-{REGION}-artifacts"
    artifact = f"arn:aws:s3:::{artifact_name}"
    receipts = f"arn:aws:s3:::{PROJECT}-{account}-{REGION}-receipts"
    tables = [arn("dynamodb", f"table/{STACK}-{n}-*") for n in ("Expenses", "Budgets")]
    functions = [arn("lambda", f"function:{PROJECT}-{n}") for n in
                 ("expense-api", "receipt-processor", "weekly-summary")]
    topic = arn("sns", f"{PROJECT}-expense-alerts")
    log_groups = [arn("logs", f"log-group:/aws/lambda/{PROJECT}-{n}") for n in
                  ("expense-api", "receipt-processor", "weekly-summary")]
    log_groups.append(arn("logs", f"log-group:{STACK}-ApiLogs-*"))
    logs = [item + suffix for item in log_groups for suffix in ("", ":*")]
    schedule_group = arn("scheduler", f"schedule-group/{STACK}-ScheduleGroup-*")
    schedule = arn("scheduler", f"schedule/{STACK}-ScheduleGroup-*/{STACK}-WeeklySchedule-*")
    schedule_in_group = arn("scheduler", f"schedule/{STACK}-ScheduleGroup-*/*")
    api_root = f"arn:aws:apigateway:{REGION}::/apis"
    pool = arn("cognito-idp", f"userpool/{pool_id}")
    docs = {}
    docs["deployment-user-policy.json"] = policy(
        statement("ChangeSetsUsingExecutionRole", ["cloudformation:CreateChangeSet"], stack,
                  condition={"StringEquals": {"cloudformation:RoleArn": execution}}),
        statement("ServerlessTransform", ["cloudformation:CreateChangeSet"],
                  f"arn:aws:cloudformation:{REGION}:aws:transform/Serverless-2016-10-31"),
        statement("OperateOnlyApplicationStack", ["cloudformation:DescribeStacks", "cloudformation:DescribeStackEvents",
                  "cloudformation:DescribeStackResource", "cloudformation:DescribeStackResources",
                  "cloudformation:ListStackResources", "cloudformation:GetTemplate", "cloudformation:DescribeChangeSet",
                  "cloudformation:ExecuteChangeSet", "cloudformation:DeleteChangeSet", "cloudformation:CancelUpdateStack"], stack),
        statement("DeleteOrRecoverUsingExecutionRole", ["cloudformation:DeleteStack", "cloudformation:ContinueUpdateRollback"],
                  stack, condition={"StringEquals": {"cloudformation:RoleArn": execution}}),
        statement("ValidateTemplates", ["cloudformation:ValidateTemplate", "cloudformation:GetTemplateSummary"], "*"),
        statement("PassOnlyExecutionRole", ["iam:PassRole"], execution, regional=False,
                  condition={"StringEquals": {"iam:PassedToService": "cloudformation.amazonaws.com"}}),
        statement("ArtifactBucketLocation", ["s3:GetBucketLocation"], artifact),
        # HeadBucket is authorized as s3:ListBucket but carries no s3:prefix, so the
        # prefix-conditioned statement below can never allow it. This also permits an
        # unfiltered key listing of the dedicated artifact bucket (never receipts).
        statement("HeadArtifactBucket", ["s3:ListBucket"], artifact),
        statement("ListArtifactPrefix", ["s3:ListBucket"], artifact,
                  condition={"StringLike": {"s3:prefix": [STACK, f"{STACK}/*"]}}),
        statement("ManageDeploymentArtifacts", ["s3:GetObject", "s3:GetObjectVersion", "s3:GetObjectTagging", "s3:PutObject", "s3:DeleteObject",
                  "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"], f"{artifact}/{STACK}/*"),
    )
    docs["cloudformation-trust-policy.json"] = {
        "Version": "2012-10-17", "Statement": [{"Effect": "Allow",
        "Principal": {"Service": "cloudformation.amazonaws.com"}, "Action": "sts:AssumeRole"}]}

    role_statements = []
    for name in ROLES:
        role_statements.append(statement(f"CreateBounded{name}", ["iam:CreateRole", "iam:PutRolePermissionsBoundary",
            "iam:PutRolePolicy", "iam:UpdateAssumeRolePolicy"],
            role_arns[name], regional=False, condition={"ArnEquals": {"iam:PermissionsBoundary": boundary[name]}}))
    role_statements.extend([
        statement("ManageOnlyApplicationRoles", ["iam:GetRole", "iam:DeleteRole", "iam:UpdateRole",
            "iam:GetRolePolicy", "iam:DeleteRolePolicy",
            "iam:ListRolePolicies", "iam:ListAttachedRolePolicies", "iam:TagRole", "iam:UntagRole", "iam:ListRoleTags"],
            list(role_arns.values()), regional=False),
        statement("PassLambdaRoles", ["iam:PassRole"], [role_arns[n] for n in ROLES[:3]], regional=False,
            condition={"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}}),
        statement("PassSchedulerRole", ["iam:PassRole"], role_arns["SchedulerRole"], regional=False,
            condition={"StringEquals": {"iam:PassedToService": "scheduler.amazonaws.com"}}),
        {"Sid": "NeverRemoveRuntimeBoundaries", "Effect": "Deny", "Action": "iam:DeleteRolePermissionsBoundary",
            "Resource": list(role_arns.values())},
    ])
    docs["cloudformation-iam-policy.json"] = policy(*role_statements)
    docs["cloudformation-storage-policy.json"] = policy(
        statement("ReadPackagedArtifacts", ["s3:GetObject", "s3:GetObjectVersion"], f"{artifact}/{STACK}/*"),
        statement("ArtifactBucketLocation", ["s3:GetBucketLocation"], artifact),
        statement("CreateReceiptBucketInSydney", ["s3:CreateBucket"], receipts,
                  condition={"StringEquals": {"s3:LocationConstraint": REGION}}),
        statement("ConfigureReceiptBucket", ["s3:GetBucketLocation", "s3:ListBucket", "s3:DeleteBucket",
            "s3:GetBucketVersioning", "s3:PutBucketVersioning", "s3:GetBucketNotification", "s3:PutBucketNotification",
            "s3:GetBucketOwnershipControls", "s3:PutBucketOwnershipControls", "s3:GetBucketPublicAccessBlock",
            "s3:PutBucketPublicAccessBlock", "s3:GetEncryptionConfiguration", "s3:PutEncryptionConfiguration",
            "s3:GetBucketCORS", "s3:PutBucketCORS", "s3:GetLifecycleConfiguration", "s3:PutLifecycleConfiguration",
            "s3:GetBucketTagging", "s3:PutBucketTagging", "s3:GetBucketPolicy", "s3:PutBucketPolicy",
            "s3:DeleteBucketPolicy", "s3:GetBucketAcl"], receipts),
        statement("ManageApplicationTables", ["dynamodb:CreateTable", "dynamodb:DescribeTable", "dynamodb:UpdateTable",
            "dynamodb:DeleteTable", "dynamodb:DescribeContinuousBackups", "dynamodb:DescribeTimeToLive",
            "dynamodb:ListTagsOfResource", "dynamodb:TagResource", "dynamodb:UntagResource"], tables),
        statement("ManageAlertTopic", ["sns:CreateTopic", "sns:GetTopicAttributes", "sns:SetTopicAttributes",
            "sns:DeleteTopic", "sns:ListTagsForResource", "sns:TagResource", "sns:UntagResource"], topic),
    )
    docs["cloudformation-compute-policy.json"] = policy(
        statement("ManageFunctionsAndTriggers", ["lambda:CreateFunction", "lambda:GetFunction", "lambda:GetFunctionConfiguration",
            "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration", "lambda:DeleteFunction",
            "lambda:GetPolicy", "lambda:RemovePermission", "lambda:TagResource", "lambda:UntagResource",
            "lambda:ListTags", "lambda:PutFunctionEventInvokeConfig", "lambda:GetFunctionEventInvokeConfig",
            "lambda:UpdateFunctionEventInvokeConfig", "lambda:DeleteFunctionEventInvokeConfig"], functions),
        # SAM's EventInvokeConfig uses Qualifier $LATEST; a qualified ARN does not match
        # the unqualified function ARN above. Only these actions get the qualified ARN.
        statement("ManageLatestEventInvokeConfigs", ["lambda:PutFunctionEventInvokeConfig",
            "lambda:GetFunctionEventInvokeConfig", "lambda:UpdateFunctionEventInvokeConfig",
            "lambda:DeleteFunctionEventInvokeConfig"], [f"{function}:$LATEST" for function in functions]),
        statement("OnlyApiGatewayAndS3InvocationGrants", ["lambda:AddPermission"], functions,
            condition={"StringEquals": {"lambda:Principal": ["apigateway.amazonaws.com", "s3.amazonaws.com"]}}),
        statement("ManageScheduleGroup", ["scheduler:CreateScheduleGroup", "scheduler:GetScheduleGroup",
            "scheduler:DeleteScheduleGroup", "scheduler:ListTagsForResource", "scheduler:TagResource", "scheduler:UntagResource"], schedule_group),
        statement("ManageWeeklySchedule", ["scheduler:CreateSchedule", "scheduler:GetSchedule",
            "scheduler:UpdateSchedule", "scheduler:DeleteSchedule"], schedule),
        # The ScheduleGroup delete handler (including rollback) deletes the group's
        # schedules, authorized against schedule/<group>/*; delete only, own groups only.
        statement("DeleteSchedulesInApplicationGroup", ["scheduler:DeleteSchedule"], schedule_in_group),
        statement("ManageLogGroupsAndFilters", ["logs:CreateLogGroup", "logs:DeleteLogGroup", "logs:PutRetentionPolicy",
            "logs:DeleteRetentionPolicy", "logs:PutMetricFilter", "logs:DeleteMetricFilter", "logs:DescribeMetricFilters",
            "logs:TagResource", "logs:UntagResource", "logs:ListTagsForResource", "logs:TagLogGroup",
            "logs:UntagLogGroup", "logs:ListTagsLogGroup"], logs),
        statement("ApiAccessLogDelivery", ["logs:DescribeLogGroups", "logs:CreateLogDelivery", "logs:GetLogDelivery",
            "logs:UpdateLogDelivery", "logs:DeleteLogDelivery", "logs:ListLogDeliveries",
            "logs:PutResourcePolicy", "logs:DescribeResourcePolicies"], "*"),
        statement("ManageApplicationAlarms", ["cloudwatch:PutMetricAlarm", "cloudwatch:DescribeAlarms",
            "cloudwatch:DeleteAlarms", "cloudwatch:TagResource", "cloudwatch:UntagResource", "cloudwatch:ListTagsForResource"],
            [arn("cloudwatch", f"alarm:{STACK}-{n}-*") for n in
             ("ProcessorErrors", "ApiErrors", "SummaryErrors", "NotificationAlarm")]),
    )
    cognito_actions = ["cognito-idp:" + a for a in (
        "DescribeUserPool", "UpdateUserPool", "DeleteUserPool", "GetUserPoolMfaConfig", "SetUserPoolMfaConfig",
        "CreateUserPoolClient", "DescribeUserPoolClient", "UpdateUserPoolClient", "DeleteUserPoolClient",
        "CreateUserPoolDomain", "UpdateUserPoolDomain", "DeleteUserPoolDomain",
        "CreateManagedLoginBranding", "DescribeManagedLoginBranding", "DescribeManagedLoginBrandingByClient",
        "UpdateManagedLoginBranding", "DeleteManagedLoginBranding", "TagResource", "UntagResource", "ListTagsForResource")]
    docs["cloudformation-api-auth-policy.json"] = policy(
        *http_api_permissions(api_id, "ManageKnown"),
        statement("ManageKnownUserPool", cognito_actions, pool),
        statement("ReadCognitoDomain", ["cognito-idp:DescribeUserPoolDomain"], "*"),
    )
    docs["temporary-first-deployment-policy.json"] = policy(
        statement("CreateHttpApi", ["apigateway:POST", "apigateway:PUT"], api_root),
        *http_api_permissions("*", "ManageInitiallyUnknown"),
        # CreateUserPool has no resource type, so Resource must be "*". Creation is
        # Sydney-only; every later call on the new pool still needs the Deployment tag.
        statement("CreateUserPoolInSydney", ["cognito-idp:CreateUserPool"], "*"),
        statement("ManageInitiallyUnknownUserPool", cognito_actions, arn("cognito-idp", "userpool/*"),
                  condition={"StringEquals": {"aws:ResourceTag/Deployment": STACK}}),
        statement("BootstrapApiGatewayServiceRole", ["iam:CreateServiceLinkedRole"],
                  iam("role/aws-service-role/ops.apigateway.amazonaws.com/AWSServiceRoleForAPIGateway"), regional=False,
                  condition={"StringEquals": {"iam:AWSServiceName": "ops.apigateway.amazonaws.com"}}),
    )

    source, errors = decode(str(ROOT / "infrastructure/template.yaml"))
    if errors:
        raise ValueError(errors)
    candidate = copy.deepcopy(source)
    replacements = {"AWS::Partition": "aws", "AWS::Region": REGION, "AWS::AccountId": account,
                    "ProjectName": PROJECT}
    refs = {"Alerts": topic}
    attributes = {"Expenses.Arn": tables[0], "Budgets.Arn": tables[1], "SummaryFunction.Arn": functions[2]}

    def resolve(value):
        if isinstance(value, list):
            return [resolve(v) for v in value]
        if not isinstance(value, dict):
            return value
        if "Fn::Sub" in value:
            return re.sub(r"\$\{([^}]+)\}", lambda m: replacements[m[1]], value["Fn::Sub"])
        if "Fn::GetAtt" in value:
            attr = value["Fn::GetAtt"]
            return attributes[".".join(attr) if isinstance(attr, list) else attr]
        if "Ref" in value:
            return refs[value["Ref"]]
        return {k: resolve(v) for k, v in value.items()}

    for name in ROLES:
        props = candidate["Resources"][name]["Properties"]
        statements = [resolve(s) for p in props["Policies"] for s in p["PolicyDocument"]["Statement"]]
        for s in statements:
            s.setdefault("Condition", {}).setdefault("StringEquals", {})["aws:RequestedRegion"] = REGION
        docs[f"boundary-{name}.json"] = policy(*statements)
        props["PermissionsBoundary"] = boundary[name]
    candidate["Resources"]["Users"]["Properties"]["UserPoolTags"] = {"Deployment": STACK}
    candidate["Parameters"]["ProjectName"]["AllowedValues"] = [PROJECT]
    candidate["Globals"]["Function"]["CodeUri"] = "../../code/backend/"
    docs["template.with-boundaries.json"] = candidate

    if amplify_id:
        docs["optional-amplify-deployer-policy.json"] = policy(
            statement("ReadHostingApp", ["amplify:GetApp"], arn("amplify", f"apps/{amplify_id}")),
            statement("DeployMainBranch", ["amplify:GetBranch", "amplify:CreateDeployment", "amplify:StartDeployment"],
                      arn("amplify", f"apps/{amplify_id}/branches/main")),
            statement("InspectHostingJobs", ["amplify:GetJob", "amplify:ListJobs"],
                      [arn("amplify", f"apps/{amplify_id}/branches/main"), arn("amplify", f"apps/{amplify_id}/branches/main/jobs/*")]),
        )
    return docs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--api-id", default="REVIEW_API_ID")
    parser.add_argument("--user-pool-id", default="ap-southeast-2_REVIEW")
    parser.add_argument("--amplify-app-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    docs = generate(args.account_id, args.api_id, args.user_pool_id, args.amplify_app_id)
    args.output.mkdir(parents=True, exist_ok=True)
    docs["template.with-boundaries.json"]["Globals"]["Function"]["CodeUri"] = (
        Path(os.path.relpath(ROOT / "code/backend", args.output)).as_posix() + "/")
    for name, document in docs.items():
        (args.output / name).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(docs)} documents locally in {args.output}; no AWS calls made.")


if __name__ == "__main__":
    main()
