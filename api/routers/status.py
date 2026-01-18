# api/routers/status.py

"""
System status endpoints for the Reptilia API.
"""

import time
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    SystemStatusResponse,
    DatabaseStatusResponse,
    SensorStats,
    OutletStats,
    HabitatStats
)
from api.models.enums import SystemHealth

router = APIRouter(prefix="/status", tags=["System Status"])

# Track startup time for uptime calculation
_startup_time = time.time()

# Readings older than this are considered stale
STALE_THRESHOLD_MINUTES = 10


@router.get("", response_model=SystemStatusResponse)
def get_system_status(db: Database = Depends(get_db)):
    """Get overall system health status."""
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    # Check database connectivity
    try:
        db.command("ping")
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Get sensor stats
    all_sensors = set()
    active_sensors = set()
    stale_sensors = set()

    # Get unique sensor IDs from recent readings
    recent_readings = db.sensor_readings.find(
        {"timestamp": {"$gte": stale_cutoff}},
        {"sensor_id": 1}
    )
    for r in recent_readings:
        all_sensors.add(r["sensor_id"])
        active_sensors.add(r["sensor_id"])

    # Get sensor IDs from older readings (stale)
    older_readings = db.sensor_readings.find(
        {"timestamp": {"$lt": stale_cutoff}},
        {"sensor_id": 1}
    )
    for r in older_readings:
        sensor_id = r["sensor_id"]
        all_sensors.add(sensor_id)
        if sensor_id not in active_sensors:
            stale_sensors.add(sensor_id)

    sensor_stats = SensorStats(
        total=len(all_sensors),
        active=len(active_sensors),
        stale=len(stale_sensors)
    )

    # Get outlet stats
    outlet_states = list(db.outlet_states.find({}))
    errors = sum(1 for o in outlet_states if o.get("state") == "error")
    outlet_stats = OutletStats(
        total=len(outlet_states),
        responsive=len(outlet_states) - errors,
        errors=errors
    )

    # Get habitat stats
    habitats = list(db.habitats.find({}))
    out_of_range = 0

    for habitat in habitats:
        # Check if any sensor is out of range
        for sensor_key in ["basking_temp_sensor_id", "cool_temp_sensor_id", "humidity_sensor_id"]:
            sensor_id = habitat.get(sensor_key)
            if not sensor_id:
                continue

            # Get latest reading
            reading = db.sensor_readings.find_one(
                {"sensor_id": sensor_id},
                sort=[("timestamp", -1)]
            )
            if not reading:
                continue

            # Get threshold
            threshold = db.thresholds.find_one({"sensor_id": sensor_id})
            if not threshold:
                continue

            value = reading["value"]
            if value < threshold["min_value"] or value > threshold["max_value"]:
                out_of_range += 1
                break  # Count habitat only once

    habitat_stats = HabitatStats(
        total=len(habitats),
        in_range=len(habitats) - out_of_range,
        out_of_range=out_of_range
    )

    # Determine overall health
    if db_status == "disconnected":
        health = SystemHealth.UNHEALTHY
    elif out_of_range > 0 or errors > 0 or len(stale_sensors) > 0:
        health = SystemHealth.DEGRADED
    else:
        health = SystemHealth.HEALTHY

    uptime = int(time.time() - _startup_time)

    return SystemStatusResponse(
        status=health,
        database=db_status,
        sensors=sensor_stats,
        outlets=outlet_stats,
        habitats=habitat_stats,
        uptime_seconds=uptime
    )


@router.get("/database", response_model=DatabaseStatusResponse)
def check_database(db: Database = Depends(get_db)):
    """Check database connectivity."""
    try:
        db.command("ping")
        collections = db.list_collection_names()
        return DatabaseStatusResponse(
            connected=True,
            database=db.name,
            collections=collections
        )
    except Exception as e:
        return DatabaseStatusResponse(
            connected=False,
            database=db.name,
            collections=[]
        )
