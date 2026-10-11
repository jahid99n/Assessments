"""Offline syntax, action-spelling, policy-size and regional-guard checks.

Not AWS Access Analyzer, an IAM simulator, or proof of deployment permissions.
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def reject_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def validate(folder):
    reference = json.loads((HERE / "action-reference.json").read_text(encoding="utf-8"))
    checked = {}
    for path in sorted(folder.glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)
        if path.name in {"template.with-boundaries.json", "action-reference.json", "validation-results.json"} or path.name.startswith("."):
            continue
        assert doc["Version"] == "2012-10-17", path.name
        assert set(doc) == {"Version", "Statement"}, path.name
        assert isinstance(doc["Statement"], list) and doc["Statement"], path.name
        trust = path.name == "cloudformation-trust-policy.json"
        size = len(json.dumps(doc, separators=(",", ":")))
        assert size <= (2048 if trust else 6144), (path.name, size)
        sids = []
        for s in doc["Statement"]:
            assert s["Effect"] in {"Allow", "Deny"}
            if "Sid" in s:
                sids.append(s["Sid"])
            actions = s["Action"] if isinstance(s["Action"], list) else [s["Action"]]
            assert actions
            if trust:
                assert s["Principal"] == {"Service": "cloudformation.amazonaws.com"}
                assert actions == ["sts:AssumeRole"] and "Resource" not in s
                continue
            assert "Principal" not in s
            resources = s["Resource"] if isinstance(s["Resource"], list) else [s["Resource"]]
            assert resources and all(r == "*" or r.startswith("arn:aws:") for r in resources)
            for action in actions:
                assert "*" not in action, (path.name, "Wildcard action", action)
                service, name = action.split(":", 1)
                assert name in reference["services"][service]["actions"], (path.name, "Unknown action", action)
                if s["Effect"] == "Allow" and service != "iam":
                    assert s.get("Condition", {}).get("StringEquals", {}).get("aws:RequestedRegion") == "ap-southeast-2", (path.name, action)
        assert len(sids) == len(set(sids)), (path.name, "Duplicate Sid")
        checked[path.name] = {"statements": len(doc["Statement"]), "compactCharacters": size, "result": "PASS"}
    assert checked, "No policies found"
    return checked


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", nargs="?", type=Path, default=HERE)
    args = parser.parse_args()
    result = validate(args.folder)
    print(json.dumps(result, indent=2))
    print(f"PASS: {len(result)} policy documents. Offline checks only; AWS authorization unverified.")
