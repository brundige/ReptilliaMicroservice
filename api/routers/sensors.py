# api/routers/sensors.py

"""
Sensor endpoints for the Reptilia API.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends,  Query
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    SensorStatusResponse,
    SensorReadingsListResponse,
    SensorReadingResponse,
    SensorReadingCreate,
    ThresholdInfo
)
from api.models.enums import SensorStatus, SensorUnit, ThresholdStatus

router = APIRouter(prefix="/sensors", tags=["Sensors"])

# Readings older than this are considered stale
STALE_THRESHOLD_MINUTES = 10


@router.get("/{sensor_id}/status", response_model=SensorStatusResponse)
def get_sensor_status(sensor_id: str, db: Database = Depends(get_db)):
    """Get current status of a sensor."""
    # Get latest reading
    latest = db.sensor_readings.find_one(
        {"sensor_id": sensor_id},
        sort=[("timestamp", -1)]
    )

    if not latest:
        return SensorStatusResponse(
            sensor_id=sensor_id,
            status=SensorStatus.NO_DATA,
            is_valid=False,
            is_stale=True,
            threshold_status=ThresholdStatus.UNKNOWN
        )

    # Check if stale
    now = datetime.now(timezone.utc)
    reading_time = latest["timestamp"]
    if reading_time.tzinfo is None:
        reading_time = reading_time.replace(tzinfo=timezone.utc)

    is_stale = (now - reading_time) > timedelta(minutes=STALE_THRESHOLD_MINUTES)
    status = SensorStatus.STALE if is_stale else SensorStatus.ACTIVE

    # Get threshold for this sensor
    threshold = db.thresholds.find_one({"sensor_id": sensor_id})
    threshold_info = None
    threshold_status = ThresholdStatus.UNKNOWN

    if threshold:
        threshold_info = ThresholdInfo(
            min=threshold["min_value"],
            max=threshold["max_value"],
            zone_type=threshold["zone_type"]
        )
        value = latest["value"]
        if value < threshold["min_value"]:
            threshold_status = ThresholdStatus.TOO_LOW
        elif value > threshold["max_value"]:
            threshold_status = ThresholdStatus.TOO_HIGH
        else:
            threshold_status = ThresholdStatus.OK

    return SensorStatusResponse(
        sensor_id=sensor_id,
        status=status,
        latest_value=latest["value"],
        latest_timestamp=latest["timestamp"],
        is_valid=latest.get("is_valid", True),
        is_stale=is_stale,
        threshold_status=threshold_status,
        threshold=threshold_info
    )


@router.get("/{sensor_id}/readings", response_model=SensorReadingsListResponse)
def get_sensor_readings(
    sensor_id: str,
    hours: int = Query(default=24, ge=1, le=720),
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    db: Database = Depends(get_db)
):
    """Get historical readings for a sensor."""
    # Use explicit times if provided, otherwise use hours
    if start_time and end_time:
        query_start = start_time
        query_end = end_time
    else:
        query_end = datetime.now(timezone.utc)
        query_start = query_end - timedelta(hours=hours)

    readings = list(db.sensor_readings.find({
        "sensor_id": sensor_id,
        "timestamp": {"$gte": query_start, "$lte": query_end}
    }).sort("timestamp", 1))

    return SensorReadingsListResponse(
        sensor_id=sensor_id,
        readings=[
            SensorReadingResponse(
                value=r["value"],
                timestamp=r["timestamp"],
                unit=SensorUnit(r["unit"]),
                is_valid=r.get("is_valid", True)
            )
            for r in readings
        ],
        count=len(readings)
    )


@router.post("/{sensor_id}/readings", status_code=201)
def submit_sensor_reading(
    sensor_id: str,
    reading: SensorReadingCreate,
    db: Database = Depends(get_db)
):
    """Submit a new sensor reading (for external sensor integrations)."""
    # Map unit string to enum value
    unit_map = {
        "celsius": "°C",
        "fahrenheit": "°F",
        "percent": "%"
    }
    unit = unit_map.get(reading.unit.lower(), reading.unit)

    doc = {
        "sensor_id": sensor_id,
        "value": reading.value,
        "timestamp": reading.timestamp or datetime.now(timezone.utc),
        "unit": unit,
        "is_valid": True
    }

    db.sensor_readings.insert_one(doc)

    return {"status": "created", "sensor_id": sensor_id, "value": reading.value}
