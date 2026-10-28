#!/usr/bin/env python3
"""Simulated GPS device sender for Mimamori Test."""

from __future__ import annotations

import math
import os
import random
import time

import httpx

SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000").rstrip("/")
DEVICE_ID = os.getenv("DEVICE_ID", "M5STICK-SIM-001")
API_KEY = os.getenv("DEVICE_API_KEY", "dev-device-key-change-me")
INTERVAL_SEC = float(os.getenv("INTERVAL_SEC", "5"))
INITIAL_LAT = float(os.getenv("INITIAL_LAT", "35.681236"))
INITIAL_LON = float(os.getenv("INITIAL_LON", "139.767125"))
STEP_MAX_M = float(os.getenv("STEP_MAX_M", "15"))

lat = INITIAL_LAT
lon = INITIAL_LON


def step() -> tuple[float, float]:
    global lat, lon
    dlat = (random.uniform(-1, 1)) * (STEP_MAX_M / 111000.0)
    dlon = (random.uniform(-1, 1)) * (STEP_MAX_M / (111000.0 * math.cos(math.radians(lat))))
    lat += dlat
    lon += dlon
    lat = min(max(lat, INITIAL_LAT - 0.005), INITIAL_LAT + 0.005)
    lon = min(max(lon, INITIAL_LON - 0.005), INITIAL_LON + 0.005)
    return lat, lon


def main() -> None:
    url = f"{SERVER_URL}/api/v1/locations"
    headers = {"X-API-Key": API_KEY}
    print(f"Simulator starting: device={DEVICE_ID} url={url} interval={INTERVAL_SEC}s")
    while True:
        latitude, longitude = step()
        payload = {
            "device_id": DEVICE_ID,
            "latitude": latitude,
            "longitude": longitude,
            "timestamp": int(time.time() * 1000),
            "accuracy_m": None,
            "fix_valid": True,
            "data_source": "simulated",
        }
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.post(url, json=payload, headers=headers)
            if resp.status_code == 201:
                data = resp.json()
                print(f"[OK] {data['received_at']} lat={latitude:.6f} lon={longitude:.6f}")
            else:
                print(f"[HTTP {resp.status_code}] {resp.text}")
        except Exception as exc:  # noqa: BLE001
            print(f"[ERROR] {exc}")
        time.sleep(INTERVAL_SEC)


if __name__ == "__main__":
    main()
