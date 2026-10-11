"""Live AWS smoke test for the deployed stack. Run it yourself; it is never run by tests.

    python code/integration/live_smoke.py signup     # once: creates a self-service test user
    python code/integration/live_smoke.py confirm    # enter the emailed code
    python code/integration/live_smoke.py run [--receipt PATH] [--delete-user]

Passwords are read with getpass and tokens stay in memory. Neither is printed or
written. Results (status codes and pass/fail only, no tokens, no email address) go
to report/stage5-live-aws-results.json. All expenses the script creates are deleted
at the end; --delete-user also deletes the test user with its own access token.
Optional second user (isolation check): set SMOKE_SECOND_EMAIL and you will be
prompted for its password.
"""
import argparse
import base64
import datetime
import getpass
import hashlib
import hmac
import json
import os
import re
import sys
import time
import uuid
from pathlib import Path

import boto3
import requests
from botocore import UNSIGNED
from botocore.config import Config

ROOT = Path(__file__).resolve().parents[2]
REGION = "ap-southeast-2"
STACK = "ict5205-expenses"
TEST_MONTH = "2026-01"  # a closed month keeps the budget arithmetic isolated

# RFC 5054 3072-bit group, as used by Cognito USER_SRP_AUTH.
N_HEX = (
    "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD129024E088A67CC74020BBEA63B139B22514A08798E3404DD"
    "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
    "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3DC2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
    "83655D23DCA3AD961C62F356208552BB9ED529077096966D670C354E4ABC9804F1746C08CA18217C32905E462E36CE3B"
    "E39E772C180E86039B2783A2EC07A28FB5C55DF06F4C52C9DE2BCBF6955817183995497CEA956AE515D2261898FA0510"
    "15728E5A8AAAC42DAD33170D04507A33A85521ABDF1CBA64ECFB850458DBEF0A8AEA71575D060C7DB3970F85A6E1E4C7"
    "ABF5AE8CDB0933D71E8C94E04A25619DCEE3D2261AD2EE6BF12FFA06D98A0864D87602733EC86A64521F2B18177B200C"
    "BBE117577A615D6C770988C0BAD946E208E24FA074E5AB3143DB5BFCE0FD108E4B82D120A93AD2CAFFFFFFFFFFFFFFFF")
N = int(N_HEX, 16)
G = 2


def _sha_hex(data):
    return hashlib.sha256(data).hexdigest().rjust(64, "0")


def _pad_hex(value):
    text = value if isinstance(value, str) else format(value, "x")
    if len(text) % 2:
        text = "0" + text
    elif text[0] in "89abcdefABCDEF":
        text = "00" + text
    return text


def _hex_hash(text):
    return _sha_hex(bytes.fromhex(text))


K = int(_hex_hash("00" + N_HEX + "0" + format(G, "x")), 16)


def srp_login(client, pool_id, client_id, username, password):
    """Cognito USER_SRP_AUTH; returns the AuthenticationResult (kept in memory)."""
    small_a = int.from_bytes(os.urandom(128), "big") % N
    big_a = pow(G, small_a, N)
    first = client.initiate_auth(ClientId=client_id, AuthFlow="USER_SRP_AUTH",
                                 AuthParameters={"USERNAME": username, "SRP_A": format(big_a, "x")})
    params = first["ChallengeParameters"]
    user_id, salt, big_b = params["USER_ID_FOR_SRP"], params["SALT"], int(params["SRP_B"], 16)
    u = int(_hex_hash(_pad_hex(big_a) + _pad_hex(big_b)), 16)
    pool_name = pool_id.split("_", 1)[1]
    x = int(_hex_hash(_pad_hex(salt) + _sha_hex(f"{pool_name}{user_id}:{password}".encode())), 16)
    s = pow(big_b - K * pow(G, x, N), small_a + u * x, N)
    prk = hmac.new(bytes.fromhex(_pad_hex(format(u, "x"))), bytes.fromhex(_pad_hex(s)), hashlib.sha256).digest()
    key = hmac.new(prk, b"Caldera Derived Key\x01", hashlib.sha256).digest()[:16]
    timestamp = re.sub(r" 0(\d) ", r" \1 ", datetime.datetime.now(datetime.UTC).strftime("%a %b %d %H:%M:%S UTC %Y"))
    message = pool_name.encode() + user_id.encode() + base64.b64decode(params["SECRET_BLOCK"]) + timestamp.encode()
    signature = base64.b64encode(hmac.new(key, message, hashlib.sha256).digest()).decode()
    second = client.respond_to_auth_challenge(
        ClientId=client_id, ChallengeName="PASSWORD_VERIFIER",
        ChallengeResponses={"USERNAME": user_id, "TIMESTAMP": timestamp, "PASSWORD_CLAIM_SECRET_BLOCK": params["SECRET_BLOCK"],
                            "PASSWORD_CLAIM_SIGNATURE": signature})
    if "AuthenticationResult" not in second:
        raise SystemExit(f"Unexpected Cognito challenge: {second.get('ChallengeName')}")
    return second["AuthenticationResult"]


def public_cognito():
    """SignUp/ConfirmSignUp/InitiateAuth/DeleteUser need no AWS credentials; never sign them."""
    return boto3.Session(region_name=REGION).client("cognito-idp", config=Config(signature_version=UNSIGNED))


def stack_outputs(profile):
    session = boto3.Session(profile_name=profile, region_name=REGION) if profile else boto3.Session(region_name=REGION)
    stack = session.client("cloudformation").describe_stacks(StackName=STACK)["Stacks"][0]
    return {o["OutputKey"]: o["OutputValue"] for o in stack["Outputs"]}


def ask_email(given, prompt="Test user email: "):
    email = (given or "").strip()
    while not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        email = input(prompt).strip()
    return email


def ask_password(prompt):
    password = ""
    while not password:
        password = getpass.getpass(prompt)
    return password


class Results:
    def __init__(self):
        self.checks = []

    def check(self, name, ok, detail=""):
        self.checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        return ok


def run(args, out):
    cognito = public_cognito()
    email = ask_email(args.email)
    try:
        tokens = srp_login(cognito, out["UserPoolId"], out["UserClientId"], email, ask_password("Test user password: "))
    except cognito.exceptions.ClientError as error:
        raise SystemExit(f"Sign-in failed: {error.response['Error']['Code']} - {error.response['Error']['Message']}")
    api = out["ApiUrl"].rstrip("/")
    session = requests.Session()
    session.headers.update({"Authorization": tokens["IdToken"], "Content-Type": "application/json"})
    r = Results()
    created = []

    def call(method, path, body=None, auth=True, **kw):
        sender = session if auth else requests
        return sender.request(method, api + path, data=None if body is None else json.dumps(body), timeout=30, **kw)

    try:
        r.check("Cognito SRP sign-in returned an ID token", bool(tokens.get("IdToken")))
        r.check("No token -> 401", call("GET", "/expenses", auth=False).status_code == 401)
        tampered = tokens["IdToken"][:-4] + ("AAAA" if not tokens["IdToken"].endswith("AAAA") else "BBBB")
        r.check("Tampered JWT -> 401", requests.get(api + "/expenses", headers={"Authorization": tampered}, timeout=30).status_code == 401)
        listing = call("GET", "/expenses")
        r.check("Authenticated GET /expenses -> 200", listing.status_code == 200, str(listing.status_code))

        tag = f"SMOKE-{uuid.uuid4().hex[:8]}"
        bad = call("POST", "/expenses", {"merchant": tag, "receiptDate": "2026-13-45", "total": "-1"})
        r.check("Invalid expense -> 400", bad.status_code == 400, str(bad.status_code))
        one = call("POST", "/expenses", {"merchant": f"{tag} A", "receiptDate": f"{TEST_MONTH}-10", "total": "40.10", "gst": "3.65", "category": "Groceries"})
        two = call("POST", "/expenses", {"merchant": f"{tag} B", "receiptDate": f"{TEST_MONTH}-20", "total": "19.95", "category": "Dining"})
        for resp in (one, two):
            if resp.status_code == 201:
                created.append(resp.json()["expenseId"])
        r.check("POST /expenses x2 -> 201", one.status_code == two.status_code == 201, f"{one.status_code},{two.status_code}")
        if len(created) == 2:
            a, b = created
            detail = call("GET", f"/expenses/{a}")
            r.check("GET /expenses/{id} -> 200 with saved total", detail.status_code == 200 and str(detail.json().get("total")) in {"40.1", "40.10"})
            updated = call("PUT", f"/expenses/{a}", {"total": "45.50", "category": "Health"})
            r.check("PUT /expenses/{id} updates total and category", updated.status_code == 200
                    and str(updated.json().get("total")) in {"45.5", "45.50"} and updated.json().get("category") == "Health")
            month = call("GET", f"/expenses?month={TEST_MONTH}")
            ids = {item["expenseId"] for item in month.json().get("items", [])} if month.status_code == 200 else set()
            r.check("Month-filtered list contains both test expenses", {a, b} <= ids)
            budget = call("PUT", "/budget", {"monthlyLimit": "100.00", "month": TEST_MONTH})
            view = budget.json() if budget.status_code == 200 else {}
            # 45.50 + 19.95 = 65.45 spent; 34.55 remaining; 65.45 % utilisation.
            r.check("PUT /budget -> 200", budget.status_code == 200, str(budget.status_code))
            r.check("Budget spent = 65.45", str(view.get("spent")) == "65.45", str(view.get("spent")))
            r.check("Budget remaining = 34.55", str(view.get("remaining")) == "34.55", str(view.get("remaining")))
            r.check("Budget utilisation = 65.45%", str(view.get("utilisation")) == "65.45", str(view.get("utilisation")))
            r.check("Budget email/summaries stay off", view.get("weeklySummary") is False and not view.get("email"))
            again = call("GET", f"/budget?month={TEST_MONTH}")
            r.check("GET /budget matches PUT view", again.status_code == 200 and again.json().get("spent") == view.get("spent"))
            stats = call("GET", "/stats?months=12")
            r.check("GET /stats -> 200 with thisMonth summary", stats.status_code == 200 and "thisMonth" in stats.json())

            if os.environ.get("SMOKE_SECOND_EMAIL"):
                other = srp_login(cognito, out["UserPoolId"], out["UserClientId"], os.environ["SMOKE_SECOND_EMAIL"],
                                  ask_password("Second user password: "))
                foreign = requests.get(api + f"/expenses/{a}", headers={"Authorization": other["IdToken"]}, timeout=30)
                r.check("Second user cannot read first user's expense (404)", foreign.status_code == 404, str(foreign.status_code))
                foreign_list = requests.get(api + f"/expenses?month={TEST_MONTH}", headers={"Authorization": other["IdToken"]}, timeout=30)
                r.check("Second user's list excludes first user's expenses",
                        foreign_list.status_code == 200 and not ({a, b} & {i["expenseId"] for i in foreign_list.json().get("items", [])}))

        if args.receipt:
            path = Path(args.receipt)
            content_type = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
            issued = call("POST", "/upload-url", {"contentType": content_type})
            r.check("POST /upload-url -> 200", issued.status_code == 200, str(issued.status_code))
            if issued.status_code == 200:
                body = issued.json()
                created.append(body["expenseId"])
                upload = requests.post(body["upload"]["url"], data=body["upload"]["fields"],
                                       files={"file": (path.name, path.read_bytes(), content_type)}, timeout=60)
                r.check("Browser-style multipart upload to S3 -> 204", upload.status_code == 204, str(upload.status_code))
                status, item = "PENDING", {}
                deadline = time.time() + 180
                while status in {"PENDING", "PROCESSING"} and time.time() < deadline:
                    time.sleep(5)
                    poll = call("GET", f"/expenses/{body['expenseId']}")
                    item = poll.json() if poll.status_code == 200 else {}
                    status = item.get("status", status)
                r.check("Receipt reached PROCESSED via S3 -> Lambda -> Textract", status == "PROCESSED",
                        f"status={status}" + (f", error={item.get('errorMessage')}" if status == "FAILED" else ""))
                if status == "PROCESSED":
                    r.check("Extracted merchant/total/date present", all(item.get(k) not in (None, "") for k in ("merchant", "total", "receiptDate")),
                            f"merchant={item.get('merchant')}, total={item.get('total')}, date={item.get('receiptDate')}, category={item.get('category')}")
                    r.check("Detail includes short-lived imageUrl", "imageUrl" in item)
                # Tampering with a signed field must be rejected before anything is stored.
                tampered_fields = {**body["upload"]["fields"], "Content-Type": "text/plain"}
                rejected = requests.post(body["upload"]["url"], data=tampered_fields,
                                         files={"file": ("x.txt", b"not an image", "text/plain")}, timeout=60)
                r.check("Tampered signed Content-Type rejected by S3 policy", rejected.status_code in {400, 403}, str(rejected.status_code))
    finally:
        for expense_id in created:
            deleted = call("DELETE", f"/expenses/{expense_id}")
            gone = call("GET", f"/expenses/{expense_id}")
            r.check(f"DELETE test expense {expense_id[:8]} then 404", deleted.status_code == 200 and gone.status_code == 404,
                    f"{deleted.status_code},{gone.status_code}")
        if args.delete_user:
            cognito.delete_user(AccessToken=tokens["AccessToken"])
            r.check("Temporary test user deleted (self-service DeleteUser)", True)

    passed = sum(c["result"] == "PASS" for c in r.checks)
    report = {"generatedAt": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"), "stack": STACK, "region": REGION,
              "apiUrl": api, "userPoolId": out["UserPoolId"], "receiptTested": bool(args.receipt),
              "isolationTested": bool(os.environ.get("SMOKE_SECOND_EMAIL")), "passed": passed, "failed": len(r.checks) - passed,
              "checks": r.checks, "note": "Generated by code/integration/live_smoke.py against the live stack. No tokens or emails recorded."}
    (ROOT / "report/stage5-live-aws-results.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(r.checks)} checks passed; written to report/stage5-live-aws-results.json")
    return 0 if passed == len(r.checks) else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["signup", "confirm", "run"])
    parser.add_argument("--email")
    parser.add_argument("--profile", default="expense-deploy", help="only used to read stack outputs")
    parser.add_argument("--receipt", help="synthetic JPEG/PNG receipt to upload")
    parser.add_argument("--delete-user", action="store_true")
    args = parser.parse_args()
    out = stack_outputs(args.profile)
    cognito = public_cognito()
    if args.command == "signup":
        email = ask_email(args.email, "Test user email (you must be able to read it): ")
        password = ask_password("New password (12+ chars, upper, lower, number, symbol): ")
        cognito.sign_up(ClientId=out["UserClientId"], Username=email, Password=password,
                        UserAttributes=[{"Name": "email", "Value": email}])
        print("Sign-up accepted. Check the inbox, then run: live_smoke.py confirm")
    elif args.command == "confirm":
        email = ask_email(args.email)
        cognito.confirm_sign_up(ClientId=out["UserClientId"], Username=email, ConfirmationCode=input("Emailed code: ").strip())
        print("Confirmed. Now run: live_smoke.py run --receipt code/integration/fixtures/synthetic-receipt.png --delete-user")
    else:
        sys.exit(run(args, out))


if __name__ == "__main__":
    main()
