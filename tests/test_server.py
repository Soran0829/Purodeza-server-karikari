import os
import time

from fastapi.testclient import TestClient

from server.db import connect, insert_location
from server.main import app

client = TestClient(app)
DEVICE_KEY = os.environ["DEVICE_API_KEY"]
APP_KEY = os.environ["APP_API_KEY"]
DEVICE_ID = "TEST-DEVICE-001"

HOUR_MS = 60 * 60 * 1000


def device_headers():
    return {"X-API-Key": DEVICE_KEY}


def app_headers():
    return {"X-API-Key": APP_KEY}


def valid_payload(**overrides):
    base = {
        "device_id": DEVICE_ID,
        "latitude": 35.681236,
        "longitude": 139.767125,
        "timestamp": int(time.time() * 1000),
        "accuracy_m": None,
        "fix_valid": True,
        "data_source": "simulated",
    }
    base.update(overrides)
    return base


def ingest(payload, headers=None):
    return client.post(
        "/api/v1/locations",
        json=payload,
        headers=device_headers() if headers is None else headers,
    )


def test_health():
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_startup_lifespan_runs():
    # The module-level client does not run the lifespan; verify the real startup path.
    with TestClient(app) as startup_client:
        assert startup_client.get("/api/v1/health").status_code == 200


def test_ingest_valid():
    r = ingest(valid_payload())
    assert r.status_code == 201
    data = r.json()
    assert data["device_id"] == DEVICE_ID
    assert data["data_source"] == "simulated"
    assert "received_at" in data
    assert isinstance(data["received_at"], int)
    assert isinstance(data["id"], int)


def test_ingest_invalid_latitude():
    assert ingest(valid_payload(latitude=999)).status_code == 422


def test_ingest_invalid_longitude():
    assert ingest(valid_payload(longitude=999)).status_code == 422


def test_ingest_zero_sentinel():
    assert ingest(valid_payload(latitude=0, longitude=0)).status_code == 422


def test_ingest_invalid_data_source():
    assert ingest(valid_payload(data_source="wifi")).status_code == 422


def test_ingest_device_id_too_long():
    assert ingest(valid_payload(device_id="D" * 65)).status_code == 422


def test_ingest_negative_accuracy():
    assert ingest(valid_payload(accuracy_m=-1)).status_code == 422


def test_ingest_timestamp_null():
    # Devices without an RTC (the current firmware) must send null, not uptime.
    r = ingest(valid_payload(timestamp=None))
    assert r.status_code == 201
    assert r.json()["timestamp"] is None


def test_ingest_missing_auth():
    r = client.post("/api/v1/locations", json=valid_payload())
    assert r.status_code == 401


def test_ingest_wrong_auth():
    r = ingest(valid_payload(), headers={"X-API-Key": "wrong"})
    assert r.status_code == 401


def test_ingest_app_key_rejected():
    assert ingest(valid_payload(), headers=app_headers()).status_code == 401


def test_ingest_future_timestamp():
    future = int(time.time() * 1000) + 10 * 60 * 1000
    assert ingest(valid_payload(timestamp=future)).status_code == 422


def test_ingest_old_timestamp_accepted():
    old_ts = int(time.time() * 1000) - 10 * 60 * 1000
    r = ingest(valid_payload(timestamp=old_ts))
    assert r.status_code == 201
    assert r.json()["timestamp"] == old_ts


def test_ingest_timestamp_older_than_24h_rejected():
    too_old_ts = int(time.time() * 1000) - 25 * HOUR_MS
    assert ingest(valid_payload(timestamp=too_old_ts)).status_code == 422


def test_latest_and_history():
    ingest(valid_payload())
    r = client.get(f"/api/v1/devices/{DEVICE_ID}/latest", headers=app_headers())
    assert r.status_code == 200
    assert r.json()["device_id"] == DEVICE_ID

    r = client.get(f"/api/v1/devices/{DEVICE_ID}/history?limit=5", headers=app_headers())
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) <= 5


def test_latest_unknown_device():
    r = client.get("/api/v1/devices/NO-SUCH-DEVICE/latest", headers=app_headers())
    assert r.status_code == 404


def test_read_missing_auth():
    r = client.get(f"/api/v1/devices/{DEVICE_ID}/latest")
    assert r.status_code == 401


def test_read_device_key_rejected():
    r = client.get(f"/api/v1/devices/{DEVICE_ID}/latest", headers=device_headers())
    assert r.status_code == 401


def test_history_limit_must_be_positive():
    r = client.get(f"/api/v1/devices/{DEVICE_ID}/history?limit=0", headers=app_headers())
    assert r.status_code == 422


def test_history_newest_first():
    for i, received_at in enumerate([1_000, 2_000, 3_000]):
        insert_location(
            os.environ["DATABASE_PATH"],
            valid_payload(device_id="TEST-ORDER-001", latitude=35.0 + i),
            received_at,
        )

    r = client.get("/api/v1/devices/TEST-ORDER-001/history", headers=app_headers())
    assert r.status_code == 200
    received_ats = [row["received_at"] for row in r.json()]
    assert received_ats == [3_000, 2_000, 1_000]


def test_history_since_filters_old_records():
    for received_at in [1_000, 2_000, 3_000]:
        insert_location(
            os.environ["DATABASE_PATH"],
            valid_payload(device_id="TEST-SINCE-001"),
            received_at,
        )

    r = client.get("/api/v1/devices/TEST-SINCE-001/history?since=2000", headers=app_headers())
    assert r.status_code == 200
    received_ats = [row["received_at"] for row in r.json()]
    assert received_ats == [3_000, 2_000]


def test_non_ascii_api_key_is_rejected_not_500():
    r = ingest(valid_payload(), headers={b"X-API-Key": b"\xe3\x81\x82"})
    assert r.status_code == 401


def test_latest_tolerates_invalid_legacy_row():
    # A row written by an older version / manual edit must not break reads.
    conn = connect(os.environ["DATABASE_PATH"])
    try:
        conn.execute(
            "INSERT INTO locations"
            " (device_id, latitude, longitude, timestamp, received_at,"
            " accuracy_m, fix_valid, data_source)"
            " VALUES ('LEGACY-001', 0, 0, NULL, 1, NULL, 1, 'wifi')"
        )
        conn.commit()
    finally:
        conn.close()

    r = client.get("/api/v1/devices/LEGACY-001/latest", headers=app_headers())
    assert r.status_code == 200
    assert r.json()["latitude"] == 0
    # Unknown data sources from a newer device must still be readable.
    assert r.json()["data_source"] == "wifi"

    r = client.get("/api/v1/devices/LEGACY-001/history", headers=app_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_device_id_is_trimmed():
    r = ingest(valid_payload(device_id="  SPACED-001  "))
    assert r.status_code == 201
    assert r.json()["device_id"] == "SPACED-001"

    r = client.get("/api/v1/devices/SPACED-001/latest", headers=app_headers())
    assert r.status_code == 200


def test_device_id_whitespace_only_rejected():
    assert ingest(valid_payload(device_id="   ")).status_code == 422


def test_device_id_invalid_characters_rejected():
    assert ingest(valid_payload(device_id="BAD/../ID")).status_code == 422


def test_boolean_latitude_rejected():
    assert ingest(valid_payload(latitude=True)).status_code == 422


def test_string_latitude_rejected():
    assert ingest(valid_payload(latitude="35.6")).status_code == 422


def test_string_timestamp_rejected():
    assert ingest(valid_payload(timestamp=str(int(time.time() * 1000)))).status_code == 422


def test_read_invalid_device_id_rejected():
    r = client.get("/api/v1/devices/bad%20id/latest", headers=app_headers())
    assert r.status_code == 422
