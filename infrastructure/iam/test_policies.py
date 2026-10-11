"""Offline regression checks for the proposed IAM controls, not an AWS simulator."""
import copy
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from prepare import generate, ROLES, ROOT
from validate import validate, reject_duplicates, validate_http_api_pair

ACCOUNT = "296280725059"
DOCS = generate(ACCOUNT, "abc123", "ap-southeast-2_Example", "exampleapp")


def statements(filename):
    return DOCS[filename]["Statement"]


def actions(filename):
    return {a for s in statements(filename) for a in
            (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])}


def test_all_checked_in_policies_pass_offline_validation():
    assert len(validate(HERE)) == 12


@pytest.mark.parametrize("name", ROLES)
def test_each_runtime_role_requires_its_own_boundary(name):
    s = next(s for s in statements("cloudformation-iam-policy.json") if s["Sid"] == f"CreateBounded{name}")
    expected = f"arn:aws:iam::{ACCOUNT}:policy/ExpenseTracker-{name}-Boundary"
    assert s["Condition"]["ArnEquals"]["iam:PermissionsBoundary"] == expected
    assert s["Resource"] == f"arn:aws:iam::{ACCOUNT}:role/ict5205-expenses-{name}-*"
    assert DOCS["template.with-boundaries.json"]["Resources"][name]["Properties"]["PermissionsBoundary"] == expected


def test_no_execution_role_self_management_or_iam_administration():
    permitted = actions("cloudformation-iam-policy.json")
    assert not permitted & {"iam:CreateUser", "iam:CreateAccessKey", "iam:CreatePolicy",
                           "iam:CreatePolicyVersion", "iam:AttachRolePolicy", "iam:AttachUserPolicy"}
    for s in statements("cloudformation-iam-policy.json"):
        assert "ExpenseTracker-CloudFormationExecution" not in json.dumps(s["Resource"])
    deny = next(s for s in statements("cloudformation-iam-policy.json") if s["Effect"] == "Deny")
    assert deny["Action"] == "iam:DeleteRolePermissionsBoundary"


def test_inline_policy_and_trust_changes_require_existing_boundary():
    for action in ["iam:PutRolePolicy", "iam:UpdateAssumeRolePolicy"]:
        grants = [s for s in statements("cloudformation-iam-policy.json") if action in s["Action"]]
        assert len(grants) == 4
        for s in grants:
            assert s["Condition"]["ArnEquals"]["iam:PermissionsBoundary"].endswith("-Boundary")


@pytest.mark.parametrize("sid,service", [("PassLambdaRoles", "lambda.amazonaws.com"),
                                        ("PassSchedulerRole", "scheduler.amazonaws.com")])
def test_runtime_passrole_restricted_to_intended_service(sid, service):
    s = next(s for s in statements("cloudformation-iam-policy.json") if s["Sid"] == sid)
    assert s["Condition"]["StringEquals"]["iam:PassedToService"] == service


def test_deployer_can_pass_only_execution_role_and_cannot_administer_resources():
    allowed = actions("deployment-user-policy.json")
    assert {a for a in allowed if a.startswith("iam:")} == {"iam:PassRole"}
    assert all(a.split(":")[0] in {"cloudformation", "iam", "s3"} for a in allowed)
    s = next(s for s in statements("deployment-user-policy.json") if s["Sid"] == "PassOnlyExecutionRole")
    assert s["Resource"] == f"arn:aws:iam::{ACCOUNT}:role/ExpenseTracker-CloudFormationExecution"
    assert s["Condition"]["StringEquals"]["iam:PassedToService"] == "cloudformation.amazonaws.com"
    assert "receipts" not in json.dumps(DOCS["deployment-user-policy.json"])


def test_role_parameter_required_for_changesets_delete_and_recovery():
    for action in ["cloudformation:CreateChangeSet", "cloudformation:DeleteStack", "cloudformation:ContinueUpdateRollback"]:
        candidates = [s for s in statements("deployment-user-policy.json") if action in s["Action"] and ":stack/" in s["Resource"]]
        assert len(candidates) == 1
        assert candidates[0]["Condition"]["StringEquals"]["cloudformation:RoleArn"].endswith("role/ExpenseTracker-CloudFormationExecution")
    # ExecuteChangeSet is scoped by stack; RoleArn isn't an input to that API.
    execute = next(s for s in statements("deployment-user-policy.json") if "cloudformation:ExecuteChangeSet" in s["Action"])
    assert execute["Resource"].endswith("stack/ict5205-expenses/*")
    assert "cloudformation:RoleArn" not in execute["Condition"]["StringEquals"]


def test_steady_state_auth_policy_uses_supplied_ids():
    encoded = json.dumps(DOCS["cloudformation-api-auth-policy.json"])
    assert "/apis/abc123" in encoded and "userpool/ap-southeast-2_Example" in encoded
    assert "/apis/*" not in encoded and "userpool/*" not in encoded
    assert "cognito-idp:CreateUserPool" not in actions("cloudformation-api-auth-policy.json")


@pytest.mark.parametrize("filename", ["cloudformation-api-auth-policy.json", "temporary-first-deployment-policy.json"])
def test_every_api_gateway_action_resource_pair_matches_v2_reference(filename):
    for s in statements(filename):
        for action in s["Action"]:
            if action.startswith("apigateway:"):
                for resource in s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]:
                    validate_http_api_pair(action, resource)


@pytest.mark.parametrize("action,path", [
    ("POST", "/apis/REVIEW_API_ID"),
    ("PUT", "/apis/REVIEW_API_ID/stages/$default"),
    ("PATCH", "/apis/REVIEW_API_ID/routes"),
    ("GET", "/tags/arn%3Aaws%3Aapigateway%3Aap-southeast-2%3A%3A%2Fapis%2FREVIEW_API_ID"),
    ("CreateApi", "/apis"),
    ("TagResource", "/apis/REVIEW_API_ID"),
])
def test_inapplicable_pairs_and_invented_actions_are_rejected(action, path):
    with pytest.raises(AssertionError):
        validate_http_api_pair(f"apigateway:{action}", f"arn:aws:apigateway:ap-southeast-2::{path}")


def test_default_placeholders_and_cognito_scopes_are_preserved():
    document = generate(ACCOUNT)["cloudformation-api-auth-policy.json"]
    assert "REVIEW_API_ID" in json.dumps(document)
    pool = next(s for s in document["Statement"] if s["Sid"] == "ManageKnownUserPool")
    assert pool["Resource"] == f"arn:aws:cognito-idp:ap-southeast-2:{ACCOUNT}:userpool/ap-southeast-2_REVIEW"
    reference = json.loads((HERE / "action-reference.json").read_text())["services"]["cognito-idp"]["actions"]
    for action in pool["Action"]:
        assert reference[action.split(":")[1]]["resources"] == ["userpool"]
    domain = next(s for s in document["Statement"] if s["Sid"] == "ReadCognitoDomain")
    assert domain["Resource"] == "*"
    assert reference["DescribeUserPoolDomain"]["resources"] == []


def test_bootstrap_pool_creation_and_management_require_stack_tag():
    for sid, key in [("CreateTaggedUserPool", "aws:RequestTag/Deployment"),
                     ("ManageInitiallyUnknownUserPool", "aws:ResourceTag/Deployment")]:
        s = next(s for s in statements("temporary-first-deployment-policy.json") if s["Sid"] == sid)
        assert s["Condition"]["StringEquals"][key] == "ict5205-expenses"


def test_execution_policies_have_no_expense_data_plane_or_notification_send():
    for name in DOCS:
        if name.startswith("cloudformation-") and "trust" not in name:
            assert not actions(name) & {"dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Scan",
                                       "sns:Publish", "sns:Subscribe", "textract:AnalyzeExpense", "lambda:InvokeFunction"}


def test_boundary_preserves_runtime_financial_scopes():
    assert "textract:AnalyzeExpense" in actions("boundary-ProcessorRole.json")
    assert "textract:AnalyzeExpense" not in actions("boundary-ApiRole.json")
    assert actions("boundary-SchedulerRole.json") == {"lambda:InvokeFunction"}
    assert "sns:Subscribe" not in actions("boundary-SummaryRole.json")


def test_lambda_invocation_grants_only_allow_expected_services():
    matches = [s for s in statements("cloudformation-compute-policy.json") if "lambda:AddPermission" in s["Action"]]
    assert len(matches) == 1
    assert matches[0]["Condition"]["StringEquals"]["lambda:Principal"] == ["apigateway.amazonaws.com", "s3.amazonaws.com"]


def test_candidate_only_adds_documented_controls():
    from cfnlint.decode import decode
    source, errors = decode(str(ROOT / "infrastructure/template.yaml"))
    assert not errors
    candidate = copy.deepcopy(DOCS["template.with-boundaries.json"])
    for name in ROLES:
        candidate["Resources"][name]["Properties"].pop("PermissionsBoundary")
    candidate["Resources"]["Users"]["Properties"].pop("UserPoolTags")
    candidate["Parameters"]["ProjectName"].pop("AllowedValues")
    candidate["Globals"]["Function"]["CodeUri"] = source["Globals"]["Function"]["CodeUri"]
    assert candidate == source


@pytest.mark.parametrize("account", ["123", "*", "296280725059:role/admin"])
def test_invalid_account_id_rejected(account):
    with pytest.raises(ValueError):
        generate(account)


def test_non_sydney_pool_rejected():
    with pytest.raises(ValueError):
        generate(ACCOUNT, pool_id="us-east-1_example")


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError):
        json.loads('{"Action": "iam:PassRole", "Action": "iam:*"}', object_pairs_hook=reject_duplicates)


def test_optional_amplify_scope():
    assert "optional-amplify-deployer-policy.json" not in generate(ACCOUNT)
    assert "amplify:CreateApp" not in actions("optional-amplify-deployer-policy.json")
    assert "amplify:UpdateApp" not in actions("optional-amplify-deployer-policy.json")
    for s in statements("optional-amplify-deployer-policy.json"):
        assert "/exampleapp" in json.dumps(s["Resource"])


def test_sam_expansion_offline_preserves_resource_count_and_boundaries(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-2")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    import botocore.httpsession
    from samtranslator.translator.transform import transform
    candidate = copy.deepcopy(DOCS["template.with-boundaries.json"])
    candidate["Globals"]["Function"]["CodeUri"] = {"Bucket": "offline-placeholder", "Key": "backend.zip"}

    class NoManagedPolicies:
        def load(self):
            raise AssertionError("AWS managed-policy lookup forbidden")

    with patch.object(botocore.httpsession.URLLib3Session, "send", side_effect=AssertionError("Network forbidden")):
        expanded = transform(candidate, {"ProjectName": "smart-expense", "FrontendOrigin": "https://example.invalid",
                                        "PrivateEmailEnabled": "false"}, NoManagedPolicies())
    assert len(expanded["Resources"]) == 44
    assert not any(r["Type"] == "AWS::CloudFormation::Stack" for r in expanded["Resources"].values())
    for name in ROLES:
        assert expanded["Resources"][name]["Properties"]["PermissionsBoundary"].endswith(f"ExpenseTracker-{name}-Boundary")
