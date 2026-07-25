import hashlib
from typing import Any


def sign_payload(payload: dict[str, Any], password: str) -> str:
    values = {
        key: value
        for key, value in payload.items()
        if key != "Token" and not isinstance(value, (dict, list))
    }
    values["Password"] = password
    raw = "".join(str(values[key]) for key in sorted(values))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def verify_payload(payload: dict[str, Any], password: str) -> bool:
    token = payload.get("Token")
    return isinstance(token, str) and token.lower() == sign_payload(payload, password).lower()
