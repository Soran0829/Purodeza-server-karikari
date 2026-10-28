from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timestamp INTEGER,
    received_at INTEGER NOT NULL,
    accuracy_m REAL,
    fix_valid INTEGER NOT NULL,
    data_source TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_locations_device_received
    ON locations (device_id, received_at DESC);
"""

INSERT_SQL = """
INSERT INTO locations
    (device_id, latitude, longitude, timestamp,
     received_at, accuracy_m, fix_valid, data_source)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

LATEST_SQL = (
    "SELECT * FROM locations WHERE device_id = ? "
    "ORDER BY received_at DESC, id DESC LIMIT 1"
)

HISTORY_SQL = (
    "SELECT * FROM locations WHERE device_id = ? "
    "ORDER BY received_at DESC, id DESC LIMIT ?"
)

HISTORY_SINCE_SQL = (
    "SELECT * FROM locations WHERE device_id = ? AND received_at >= ? "
    "ORDER BY received_at DESC, id DESC LIMIT ?"
)


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str) -> None:
    conn = connect(db_path)
    try:
        # WAL keeps readers from blocking the writer on this single-file prototype DB.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def insert_location(db_path: str, record: Dict[str, Any], received_at: int) -> int:
    conn = connect(db_path)
    try:
        cur = conn.execute(
            INSERT_SQL,
            (
                record["device_id"],
                record["latitude"],
                record["longitude"],
                record.get("timestamp"),
                received_at,
                record.get("accuracy_m"),
                1 if record["fix_valid"] else 0,
                record["data_source"],
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "device_id": row["device_id"],
        "latitude": row["latitude"],
        "longitude": row["longitude"],
        "timestamp": row["timestamp"],
        "received_at": row["received_at"],
        "accuracy_m": row["accuracy_m"],
        "fix_valid": bool(row["fix_valid"]),
        "data_source": row["data_source"],
    }


def get_latest(db_path: str, device_id: str) -> Optional[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        row = conn.execute(LATEST_SQL, (device_id,)).fetchone()
        return row_to_dict(row) if row else None
    finally:
        conn.close()


def get_history(
    db_path: str, device_id: str, limit: int, since: Optional[int] = None
) -> List[Dict[str, Any]]:
    conn = connect(db_path)
    try:
        if since is None:
            rows = conn.execute(HISTORY_SQL, (device_id, limit)).fetchall()
        else:
            rows = conn.execute(HISTORY_SINCE_SQL, (device_id, since, limit)).fetchall()
        return [row_to_dict(r) for r in rows]
    finally:
        conn.close()
