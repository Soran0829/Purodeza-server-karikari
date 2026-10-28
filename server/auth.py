from __future__ import annotations

import hmac
from typing import Callable

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from .config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def keys_match(provided: str | None, expected: str) -> bool:
    """Constant-time API key comparison that tolerates non-ASCII input.

    ``hmac.compare_digest`` raises TypeError for non-ASCII *str* arguments.
    Header bytes above 0x7F are decoded as non-ASCII characters, so a client
    could otherwise turn an auth failure into a 500. Compare as UTF-8 bytes.
    """
    if provided is None:
        return False
    try:
        return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))
    except (UnicodeEncodeError, TypeError):
        return False


def require_key(expected: str) -> Callable:
    async def dependency(api_key: str | None = Security(api_key_header)) -> None:
        if not keys_match(api_key, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing API key",
            )

    return dependency


require_device_key = require_key(settings.device_api_key)
require_app_key = require_key(settings.app_api_key)
