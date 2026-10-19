import json
import os
import re
from urllib.parse import parse_qsl, urlsplit


SECRET_PATTERN = re.compile(
    r"(?:sk-[A-Za-z0-9_-]{16,}|AIza[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9._-]{16,}|"
    r"(?:api[_ -]?key|access[_ -]?token|password|비밀번호)\s*[:=]\s*\S+)", re.I)
AUTH_PARAMETER = re.compile(r"(?:token|api[_-]?key|session|signature|credential|password|secret|authorization|auth)", re.I)


def _check_url_credentials(text):
    for candidate in re.findall(r"https?://[^\s<>\"']+", text, flags=re.I):
        try:
            url = urlsplit(candidate)
            parameters = parse_qsl(url.query, keep_blank_values=True) + parse_qsl(url.fragment, keep_blank_values=True)
            if "?" in url.fragment:
                parameters += parse_qsl(url.fragment.split("?", 1)[1], keep_blank_values=True)
            if url.username is not None or url.password is not None or any(AUTH_PARAMETER.search(name) for name, _ in parameters):
                raise ValueError("sensitive_input_rejected")
        except ValueError:
            raise ValueError("sensitive_input_rejected") from None


def _check_urls(value):
    if isinstance(value, str):
        _check_url_credentials(value)
    elif isinstance(value, dict):
        for key, child in value.items():
            _check_urls(key)
            _check_urls(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_urls(child)


def check_sensitive_input(value):
    """Reject user/model text that appears to include credentials before sending or storing it."""
    _check_urls(value)
    encoded = json.dumps(value, ensure_ascii=False)
    keys = [secret for name, secret in os.environ.items()
            if secret and len(secret) >= 8 and
            any(tag in name.upper() for tag in ("API_KEY", "TOKEN", "SECRET", "PASSWORD"))]
    if SECRET_PATTERN.search(encoded) or any(json.dumps(secret, ensure_ascii=False)[1:-1] in encoded for secret in keys):
        raise ValueError("sensitive_input_rejected")


def normalize_origin(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError(f"invalid http(s) origin: {value}")
    host = parsed.hostname.lower()
    port = parsed.port
    default = (parsed.scheme == "http" and port in (None, 80)) or (parsed.scheme == "https" and port in (None, 443))
    return f"{parsed.scheme.lower()}://{host}" + (f":{port}" if port and not default else "")


def origin_allowed(url: str, allowed: list[str]) -> bool:
    try:
        return normalize_origin(url) in allowed
    except ValueError:
        return False

