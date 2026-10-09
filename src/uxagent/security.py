from urllib.parse import urlsplit


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

