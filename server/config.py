from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DEVICE_API_KEY = "dev-device-key-change-me"
DEFAULT_APP_API_KEY = "dev-app-key-change-me"


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {raw!r}") from exc


@dataclass(frozen=True)
class Settings:
    database_path: str = os.getenv("DATABASE_PATH", "mimamori.db")
    device_api_key: str = os.getenv("DEVICE_API_KEY", DEFAULT_DEVICE_API_KEY)
    app_api_key: str = os.getenv("APP_API_KEY", DEFAULT_APP_API_KEY)
    # Clients use this to decide when to show STALE; the server only passes it through.
    stale_threshold_ms: int = _int_env("STALE_THRESHOLD_MS", 30000)
    max_history_limit: int = _int_env("MAX_HISTORY_LIMIT", 500)

    def __post_init__(self) -> None:
        if not self.database_path.strip():
            raise RuntimeError("DATABASE_PATH must not be empty")
        if not self.device_api_key:
            raise RuntimeError("DEVICE_API_KEY must not be empty")
        if not self.app_api_key:
            raise RuntimeError("APP_API_KEY must not be empty")
        if self.stale_threshold_ms <= 0:
            raise RuntimeError("STALE_THRESHOLD_MS must be greater than 0")
        if self.max_history_limit <= 0:
            raise RuntimeError("MAX_HISTORY_LIMIT must be greater than 0")

    def using_default_keys(self) -> bool:
        """True when at least one key is still the development placeholder."""
        return (
            self.device_api_key == DEFAULT_DEVICE_API_KEY
            or self.app_api_key == DEFAULT_APP_API_KEY
        )

    def using_shared_keys(self) -> bool:
        """True when the device and app keys are identical (no role separation)."""
        return self.device_api_key == self.app_api_key


settings = Settings()
