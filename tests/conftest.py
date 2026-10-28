import os
import tempfile

import pytest

os.environ.setdefault("DEVICE_API_KEY", "test-device-key")
os.environ.setdefault("APP_API_KEY", "test-app-key")
os.environ.setdefault("DATABASE_PATH", os.path.join(tempfile.gettempdir(), "mimamori_test.db"))

db_path = os.environ["DATABASE_PATH"]


def _remove_db_files() -> None:
    # WAL mode leaves -wal / -shm side files behind.
    for suffix in ("", "-wal", "-shm"):
        path = db_path + suffix
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass


_remove_db_files()

from fastapi.testclient import TestClient  # noqa: E402

from server.db import connect, init_db  # noqa: E402
from server.main import app  # noqa: E402

init_db(db_path)


@pytest.fixture(autouse=True)
def clean_db():
    """Keep tests independent: start every test with an empty table."""
    conn = connect(db_path)
    try:
        conn.execute("DELETE FROM locations")
        conn.commit()
    finally:
        conn.close()
    yield


def pytest_sessionfinish(session, exitstatus):
    _remove_db_files()


__all__ = ["TestClient", "app"]
