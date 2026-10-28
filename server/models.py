from __future__ import annotations

import math
from typing import Annotated, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    StringConstraints,
    field_validator,
    model_validator,
)

DataSource = Literal["simulated", "gps"]

# Device ids are used as URL path segments, so keep them ASCII and free of
# separators. Leading/trailing whitespace is stripped before validation.
DEVICE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
DeviceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=64,
        pattern=DEVICE_ID_PATTERN,
    ),
]


class LocationIn(BaseModel):
    # Strict mode rejects "35.6" and true for coordinates, while still
    # accepting JSON numbers (int or float) for float fields.
    model_config = ConfigDict(strict=True)

    device_id: DeviceId
    latitude: float
    longitude: float
    timestamp: Optional[int] = None
    accuracy_m: Optional[float] = None
    fix_valid: bool
    data_source: DataSource

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("latitude must be finite")
        if value < -90 or value > 90:
            raise ValueError("latitude out of range")
        return value

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("longitude must be finite")
        if value < -180 or value > 180:
            raise ValueError("longitude out of range")
        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return value
        if isinstance(value, bool):
            raise ValueError("timestamp must be an integer or null")
        if value < 0:
            raise ValueError("timestamp must be non-negative")
        return value

    @field_validator("accuracy_m")
    @classmethod
    def validate_accuracy(cls, value: Optional[float]) -> Optional[float]:
        if value is None:
            return value
        if not math.isfinite(value):
            raise ValueError("accuracy_m must be finite")
        if value < 0:
            raise ValueError("accuracy_m must be non-negative")
        return value

    @model_validator(mode="after")
    def validate_coordinate_sentinel(self) -> "LocationIn":
        if self.latitude == 0 and self.longitude == 0:
            raise ValueError("coordinates (0,0) are not accepted")
        return self


class LocationOut(BaseModel):
    """Read model.

    Deliberately does not inherit LocationIn: re-running input validators on
    stored rows means one legacy/invalid row would turn every read into a 500.
    ``data_source`` is a plain string for the same forward-compatibility reason.
    """

    id: Optional[int] = None
    device_id: str
    latitude: float
    longitude: float
    timestamp: Optional[int] = None
    received_at: int
    accuracy_m: Optional[float] = None
    fix_valid: bool
    data_source: str
