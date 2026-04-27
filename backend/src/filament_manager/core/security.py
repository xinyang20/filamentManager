SENSITIVE_KEYS = {
    "access_code",
    "password",
    "token",
    "secret",
}


def mask_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "":
        return ""
    if len(value) <= 4:
        return "****"
    return f"****{value[-4:]}"


def redact_sensitive(value: object) -> object:
    if isinstance(value, dict):
        redacted: dict[str, object] = {}
        for key, item in value.items():
            if key.lower() in SENSITIVE_KEYS:
                redacted[key] = mask_secret(str(item)) if item is not None else None
            else:
                redacted[key] = redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    return value
