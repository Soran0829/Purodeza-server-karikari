import pytest

from server.auth import keys_match
from server.config import (
    DEFAULT_APP_API_KEY,
    DEFAULT_DEVICE_API_KEY,
    Settings,
)


def test_keys_match_allows_non_ascii_keys():
    assert keys_match("日本語キー", "日本語キー") is True
    assert keys_match("日本語キー", "別のキー") is False


def test_keys_match_missing_header():
    assert keys_match(None, "any-key") is False


def test_settings_reject_empty_api_key():
    with pytest.raises(RuntimeError):
        Settings(device_api_key="", app_api_key="app-key")


def test_settings_reject_empty_database_path():
    with pytest.raises(RuntimeError):
        Settings(database_path="   ")


def test_settings_reject_non_positive_limits():
    with pytest.raises(RuntimeError):
        Settings(stale_threshold_ms=0)
    with pytest.raises(RuntimeError):
        Settings(max_history_limit=0)


def test_settings_detects_development_defaults():
    s = Settings(
        device_api_key=DEFAULT_DEVICE_API_KEY,
        app_api_key=DEFAULT_APP_API_KEY,
    )
    assert s.using_default_keys() is True
    assert s.using_shared_keys() is False

    s = Settings(device_api_key="same-key", app_api_key="same-key")
    assert s.using_default_keys() is False
    assert s.using_shared_keys() is True
