from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Path, Query, status

from .auth import require_app_key, require_device_key
from .config import settings
from .db import get_history, get_latest, init_db, insert_location
from .models import DEVICE_ID_PATTERN, LocationIn, LocationOut

logger = logging.getLogger("mimamori.server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(settings.database_path)
    if settings.using_default_keys():
        logger.warning(
            "Using default development API keys. Set DEVICE_API_KEY and APP_API_KEY "
            "before exposing this server outside localhost."
        )
    if settings.using_shared_keys():
        logger.warning(
            "DEVICE_API_KEY and APP_API_KEY are identical; the device key can also "
            "read location data."
        )
    yield


app = FastAPI(
    title="Mimamori Test API",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


# Sync path operations so FastAPI runs the blocking sqlite3 calls in its worker
# threadpool instead of blocking the event loop.
@app.post("/api/v1/locations", status_code=status.HTTP_201_CREATED, response_model=LocationOut)
def ingest_location(
    payload: LocationIn,
    _: None = Depends(require_device_key),
) -> LocationOut:
    now_ms = int(time.time() * 1000)
    if payload.timestamp is not None:
        if payload.timestamp > now_ms + 5 * 60 * 1000:
            raise HTTPException(status_code=422, detail="timestamp is too far in the future")
        if payload.timestamp < now_ms - 24 * 60 * 60 * 1000:
            raise HTTPException(status_code=422, detail="timestamp is too old")

    received_at = now_ms
    record_id = insert_location(settings.database_path, payload.model_dump(), received_at)
    stored = payload.model_dump()
    stored["received_at"] = received_at
    stored["id"] = record_id
    return LocationOut(**stored)


@app.get("/api/v1/devices/{device_id}/latest", response_model=LocationOut)
def latest_location(
    device_id: str = Path(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN),
    _: None = Depends(require_app_key),
) -> LocationOut:
    row = get_latest(settings.database_path, device_id)
    if row is None:
        raise HTTPException(status_code=404, detail="no location for device")
    return LocationOut(**row)


@app.get("/api/v1/devices/{device_id}/history", response_model=List[LocationOut])
def location_history(
    device_id: str = Path(..., min_length=1, max_length=64, pattern=DEVICE_ID_PATTERN),
    limit: int = Query(50, ge=1, le=1000),
    since: Optional[int] = Query(None, ge=0),
    _: None = Depends(require_app_key),
) -> List[LocationOut]:
    limit = min(limit, settings.max_history_limit)
    rows = get_history(settings.database_path, device_id, limit, since)
    return [LocationOut(**row) for row in rows]
