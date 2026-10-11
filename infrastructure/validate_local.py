"""Offline SAM expansion only. Output uses a fictional artifact; NEVER deploy it."""
import json
import os
from pathlib import Path
from unittest.mock import patch

# These fixed dummy values are only for local SDK setup, never real credentials.
os.environ.update(AWS_DEFAULT_REGION="ap-southeast-2", AWS_ACCESS_KEY_ID="testing",
                  AWS_SECRET_ACCESS_KEY="testing", AWS_EC2_METADATA_DISABLED="true")
import botocore.httpsession
from cfnlint.decode import decode
from samtranslator.translator.transform import transform

root = Path(__file__).resolve().parents[1]
template, errors = decode(str(root / "infrastructure/template.yaml"))
assert not errors
template = json.loads(json.dumps(template))
# The transform expects an uploaded CodeUri. This is a structural check only.
template["Globals"]["Function"]["CodeUri"] = {"Bucket": "offline-placeholder-not-deployed", "Key": "backend.zip"}


class NoManagedPolicies:
    def load(self):
        raise AssertionError("No managed-policy lookup is needed for explicit roles")


def forbidden(*args, **kwargs):
    raise AssertionError("AWS network access forbidden during validation")


with patch.object(botocore.httpsession.URLLib3Session, "send", forbidden):
    expanded = transform(template, {"ProjectName": "smart-expense", "FrontendOrigin": "https://example.invalid", "PrivateEmailEnabled": "false"}, NoManagedPolicies())
expanded["Description"] = "OFFLINE STRUCTURAL VALIDATION ONLY - placeholder artifacts, DO NOT DEPLOY"
output = root / "report/stage4-expanded-template.json"
output.write_text(json.dumps(expanded, indent=2) + "\n", encoding="utf-8")
permissions = {name: value["Properties"] for name, value in expanded["Resources"].items() if value["Type"] == "AWS::Lambda::Permission"}
print(json.dumps({"expandedResources": len(expanded["Resources"]), "permissions": permissions}, indent=2))
