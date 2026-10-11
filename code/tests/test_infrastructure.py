"""Local structural security assertions; these do not simulate AWS IAM evaluation."""
from pathlib import Path
import pytest
from cfnlint.decode import decode

ROOT = Path(__file__).resolve().parents[2]
TEMPLATE, ERRORS = decode(str(ROOT / "infrastructure/template.yaml"))
R = TEMPLATE["Resources"]


def test_template_parses_and_preserves_architecture():
    assert not ERRORS
    assert sum(r["Type"] == "AWS::DynamoDB::Table" for r in R.values()) == 2
    assert sum(r["Type"] == "AWS::Serverless::Function" for r in R.values()) == 3
    assert not any(r["Type"].startswith(('AWS::EC2::', 'AWS::RDS::', 'AWS::ElasticLoadBalancing')) for r in R.values())
    assert TEMPLATE["Globals"]["Function"]["Runtime"] == "python3.12"
    assert TEMPLATE["Globals"]["Function"]["Timeout"] < 90
    assert TEMPLATE["Parameters"]["PrivateEmailEnabled"]["Default"] == "false"


def test_every_api_route_uses_default_jwt_authorizer():
    auth = R["Api"]["Properties"]["Auth"]
    assert auth["DefaultAuthorizer"] == "Cognito"
    assert auth["Authorizers"]["Cognito"]["JwtConfiguration"]["audience"] == [{"Ref": "UserClient"}]
    events = R["ApiFunction"]["Properties"]["Events"].values()
    assert len(events) == 9
    for event in events:
        assert event["Type"] == "HttpApi"
        assert "Auth" not in event["Properties"]
    assert not any(r["Type"] == "AWS::Lambda::Url" for r in R.values())


def test_private_versioned_encrypted_bucket_and_exact_cors():
    props = R["Receipts"]["Properties"]
    assert all(props["PublicAccessBlockConfiguration"].values())
    assert props["VersioningConfiguration"]["Status"] == "Enabled"
    assert props["BucketEncryption"]["ServerSideEncryptionConfiguration"][0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] == "AES256"
    assert props["OwnershipControls"]["Rules"][0]["ObjectOwnership"] == "BucketOwnerEnforced"
    assert props["CorsConfiguration"]["CorsRules"][0]["AllowedOrigins"] == [{"Ref": "FrontendOrigin"}]
    assert R["Api"]["Properties"]["CorsConfiguration"]["AllowOrigins"] == [{"Ref": "FrontendOrigin"}]


def test_cognito_code_flow_without_secret_or_implicit_flow():
    p = R["UserClient"]["Properties"]
    assert p["GenerateSecret"] is False
    assert p["AllowedOAuthFlows"] == ["code"]
    assert R["Users"]["Properties"]["AutoVerifiedAttributes"] == ["email"]
    assert R["LoginBranding"]["Properties"]["UseCognitoProvidedValues"] is True


def test_receipt_invocation_is_restricted_to_exact_bucket_and_account():
    p = R['ProcessorInvokePermission']['Properties']
    assert p['Principal'] == 's3.amazonaws.com'
    assert p['SourceAccount'] == {'Ref':'AWS::AccountId'}
    assert p['SourceArn'] == {'Fn::Sub':'arn:${AWS::Partition}:s3:::${ProjectName}-${AWS::AccountId}-${AWS::Region}-receipts'}
    assert R['Receipts']['DependsOn'] == 'ProcessorInvokePermission'
    assert R['Receipts']['Properties']['NotificationConfiguration']['LambdaConfigurations'][0]['Event']=='s3:ObjectCreated:*'


def test_user_pool_carries_bootstrap_deployment_tag():
    # The temporary bootstrap policy manages only pools tagged for this stack.
    assert R['Users']['Properties']['UserPoolTags'] == {'Deployment': 'ict5205-expenses'}


@pytest.mark.parametrize('role', ['ApiRole', 'ProcessorRole', 'SummaryRole', 'SchedulerRole'])
def test_each_runtime_role_has_its_administrator_owned_boundary(role):
    props = R[role]["Properties"]
    assert R[role]["Type"] == 'AWS::IAM::Role'
    assert props["PermissionsBoundary"] == {
        'Fn::Sub': f'arn:${{AWS::Partition}}:iam::${{AWS::AccountId}}:policy/ExpenseTracker-Boundary{role}'}
    # Generated names must keep matching the execution policy's ict5205-expenses-<Role>-* scope.
    assert 'RoleName' not in props and 'Path' not in props


@pytest.mark.parametrize('role', ['ApiRole', 'ProcessorRole', 'SummaryRole', 'SchedulerRole'])
def test_roles_have_no_broad_data_permissions(role):
    for policy in R[role]["Properties"]["Policies"]:
        for statement in policy["PolicyDocument"]["Statement"]:
            actions = statement["Action"]
            if isinstance(actions, str): actions = [actions]
            assert all('*' not in action for action in actions)
            if statement["Resource"] == '*':
                assert actions == ['textract:AnalyzeExpense']  # no resource-level support
            assert 'dynamodb:Scan' not in actions or role == 'SummaryRole'
            assert 'sns:SetSubscriptionAttributes' not in actions


def test_weekly_schedule_retains_sydney_dst_and_original_window():
    p = R["WeeklySchedule"]["Properties"]
    assert p["ScheduleExpression"] == 'cron(0 9 ? * MON *)'
    assert p["ScheduleExpressionTimezone"] == 'Australia/Sydney'
    assert p["FlexibleTimeWindow"]["Mode"] == 'OFF'
    assert '<aws.scheduler.scheduled-time>' in p["Target"]["Input"]
    trust=R["SchedulerRole"]["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]
    assert 'aws:SourceAccount' in trust['Condition']['StringEquals']


def test_private_topic_has_no_unfiltered_infrastructure_subscriptions():
    assert not any(r["Type"] == "AWS::SNS::Subscription" for r in R.values())
    statements=R["AlertsPolicy"]["Properties"]["PolicyDocument"]["Statement"]
    assert {s['Action'] for s in statements} == {'sns:Publish','sns:Subscribe'}
    assert all(s['Effect']=='Deny' and 'aws:PrincipalArn' in s['Condition']['ArnNotEquals'] for s in statements)


def test_harness_is_outside_lambda_and_production_entry():
    assert TEMPLATE['Globals']['Function']['CodeUri']=='../code/backend/'
    assert 'integration' not in (ROOT/'code/frontend/src/main.jsx').read_text()
    requirements=(ROOT/'code/backend/requirements.txt').read_text()
    assert 'moto' not in requirements and 'pytest' not in requirements


def test_logs_have_bounded_retention_and_sensitive_fields_are_omitted():
    logs=[r for r in R.values() if r['Type']=='AWS::Logs::LogGroup']
    assert len(logs)==4 and all(r['Properties']['RetentionInDays']==14 for r in logs)
    fmt=R['Api']['Properties']['AccessLogSettings']['Format'].lower()
    assert not any(s in fmt for s in ('authorization','email','body','querystring'))
