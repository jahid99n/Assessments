import re
from common import Problem


def identity(event):
    claims = event.get("requestContext", {}).get("authorizer", {}).get("jwt", {}).get("claims", {})
    sub = claims.get("sub", "")
    if not isinstance(sub, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", sub):
        raise Problem("Authentication required", 401)
    return sub, claims
