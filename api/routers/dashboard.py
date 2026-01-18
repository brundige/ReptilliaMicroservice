# api/routers/dashboard.py

"""
Dashboard endpoints for iPad at-a-glance monitoring and log streaming.
"""

import os
import asyncio
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import DashboardResponse, HabitatSummary
from api.models.enums import ReptileSpecies, SystemHealth

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Path to shared log file (set via LOG_FILE env var in Docker)
LOG_FILE = os.getenv("LOG_FILE", "/app/logs/service.log")

# Readings older than this are considered stale
STALE_THRESHOLD_MINUTES = 10


def celsius_to_fahrenheit(celsius: float | None) -> float | None:
    """Convert Celsius to Fahrenheit."""
    if celsius is None:
        return None
    return round((celsius * 9 / 5) + 32, 1)


def get_habitat_status(
    basking_temp: float | None,
    cool_temp: float | None,
    humidity: float | None,
    requirements: dict | None,
    is_stale: bool
) -> str:
    """Determine habitat status: ok, warning, or critical."""
    if is_stale:
        return "warning"

    if not requirements:
        return "ok" if basking_temp is not None else "warning"

    # Check if any readings are out of range
    critical = False
    warning = False

    if basking_temp is not None:
        if basking_temp < requirements.get("basking_temp_min", 0) - 5:
            critical = True
        elif basking_temp < requirements.get("basking_temp_min", 0):
            warning = True
        elif basking_temp > requirements.get("basking_temp_max", 100) + 5:
            critical = True
        elif basking_temp > requirements.get("basking_temp_max", 100):
            warning = True

    if cool_temp is not None:
        if cool_temp < requirements.get("cool_side_temp_min", 0) - 5:
            critical = True
        elif cool_temp < requirements.get("cool_side_temp_min", 0):
            warning = True
        elif cool_temp > requirements.get("cool_side_temp_max", 100) + 5:
            critical = True
        elif cool_temp > requirements.get("cool_side_temp_max", 100):
            warning = True

    if humidity is not None:
        if humidity < requirements.get("humidity_min", 0) - 10:
            critical = True
        elif humidity < requirements.get("humidity_min", 0):
            warning = True
        elif humidity > requirements.get("humidity_max", 100) + 10:
            critical = True
        elif humidity > requirements.get("humidity_max", 100):
            warning = True

    if critical:
        return "critical"
    if warning:
        return "warning"
    return "ok"


@router.get("", response_model=DashboardResponse)
def get_dashboard(db: Database = Depends(get_db)):
    """
    Get all habitats at a glance - designed for iPad monitoring.

    Returns a compact view of all habitats with current conditions,
    outlet states, and overall system health.
    """
    now = datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(minutes=STALE_THRESHOLD_MINUTES)

    # Get all habitats
    habitats = list(db.habitats.find({}))

    habitat_summaries = []
    ok_count = 0
    warning_count = 0
    critical_count = 0

    for habitat in habitats:
        habitat_id = habitat["habitat_id"]

        # Get latest readings for each sensor
        basking_reading = db.sensor_readings.find_one(
            {"sensor_id": habitat.get("basking_temp_sensor_id")},
            sort=[("timestamp", -1)]
        )
        cool_reading = db.sensor_readings.find_one(
            {"sensor_id": habitat.get("cool_temp_sensor_id")},
            sort=[("timestamp", -1)]
        )
        humidity_reading = db.sensor_readings.find_one(
            {"sensor_id": habitat.get("humidity_sensor_id")},
            sort=[("timestamp", -1)]
        )

        # Get values in Celsius
        basking_temp_c = basking_reading["value"] if basking_reading else None
        cool_temp_c = cool_reading["value"] if cool_reading else None
        humidity = humidity_reading["value"] if humidity_reading else None

        # Determine the latest reading timestamp
        reading_times = []
        if basking_reading:
            reading_times.append(basking_reading["timestamp"])
        if cool_reading:
            reading_times.append(cool_reading["timestamp"])
        if humidity_reading:
            reading_times.append(humidity_reading["timestamp"])

        last_reading = max(reading_times) if reading_times else None
        is_stale = last_reading is None or last_reading < stale_cutoff

        # Get species requirements
        requirements = db.habitat_requirements.find_one({"species": habitat.get("species")})

        # Get outlet states
        heat_lamp_state = db.outlet_states.find_one({"outlet_id": habitat.get("heat_lamp_outlet_id")})
        uvb_state = db.outlet_states.find_one({"outlet_id": habitat.get("uvb_outlet_id")})

        # Determine overall habitat status
        status = get_habitat_status(basking_temp_c, cool_temp_c, humidity, requirements, is_stale)

        if status == "ok":
            ok_count += 1
        elif status == "warning":
            warning_count += 1
        else:
            critical_count += 1

        summary = HabitatSummary(
            habitat_id=habitat_id,
            name=habitat.get("name", habitat_id),
            species=ReptileSpecies(habitat.get("species", "leopard_gecko")),
            status=status,
            basking_temp_f=celsius_to_fahrenheit(basking_temp_c),
            cool_temp_f=celsius_to_fahrenheit(cool_temp_c),
            humidity=round(humidity, 1) if humidity else None,
            heat_lamp=heat_lamp_state.get("state", "unknown") if heat_lamp_state else "unknown",
            uvb=uvb_state.get("state", "unknown") if uvb_state else "unknown",
            last_reading=last_reading
        )
        habitat_summaries.append(summary)

    # Determine system status
    try:
        db.command("ping")
        if critical_count > 0:
            system_status = SystemHealth.UNHEALTHY
        elif warning_count > 0:
            system_status = SystemHealth.DEGRADED
        else:
            system_status = SystemHealth.HEALTHY
    except Exception:
        system_status = SystemHealth.UNHEALTHY

    # Get day/night mode from stored state (if available)
    day_night_state = db.day_night_state.find_one({})
    mode = day_night_state.get("mode", "day") if day_night_state else "day"

    # Count active (unacknowledged) alerts
    active_alerts = db.alerts.count_documents({"acknowledged": False})

    return DashboardResponse(
        timestamp=now,
        system_status=system_status,
        mode=mode,
        habitats=habitat_summaries,
        active_alerts=active_alerts,
        total_habitats=len(habitats),
        habitats_ok=ok_count,
        habitats_warning=warning_count,
        habitats_critical=critical_count
    )


async def tail_log_file(lines: int = 100) -> AsyncGenerator[str, None]:
    """
    Async generator that tails the service log file.
    Yields new lines as Server-Sent Events.
    """
    # Try to read from log file
    if not os.path.exists(LOG_FILE):
        yield f"data: Log file not found: {LOG_FILE}\n\n"
        yield "data: Waiting for service to start logging...\n\n"

    # Keep track of file position
    last_position = 0

    # First, send the last N lines
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                # Read all lines and get the last N
                all_lines = f.readlines()
                recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
                for line in recent_lines:
                    yield f"data: {line.rstrip()}\n\n"
                last_position = f.tell()
        except Exception as e:
            yield f"data: Error reading log file: {e}\n\n"

    # Then continuously check for new lines
    while True:
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as f:
                    f.seek(last_position)
                    new_lines = f.readlines()
                    for line in new_lines:
                        yield f"data: {line.rstrip()}\n\n"
                    last_position = f.tell()
        except Exception as e:
            yield f"data: Error: {e}\n\n"

        # Wait before checking again
        await asyncio.sleep(1)


@router.get("/logs/stream")
async def stream_logs(lines: int = Query(default=100, ge=1, le=1000)):
    """
    Stream service logs via Server-Sent Events (SSE).

    Connect to this endpoint from your iPad to see real-time console output.

    Usage in browser/JavaScript:
        const eventSource = new EventSource('/api/dashboard/logs/stream');
        eventSource.onmessage = (event) => console.log(event.data);

    Args:
        lines: Number of recent log lines to show initially (default: 100)
    """
    return StreamingResponse(
        tail_log_file(lines),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )


@router.get("/logs/recent")
def get_recent_logs(
    lines: int = Query(default=100, ge=1, le=1000),
):
    """
    Get recent log lines (non-streaming).

    Useful for initial load or polling-based updates.

    Args:
        lines: Number of recent log lines to return (default: 100)
    """
    if not os.path.exists(LOG_FILE):
        return {
            "logs": [f"Log file not found: {LOG_FILE}"],
            "count": 1
        }

    try:
        with open(LOG_FILE, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return {
                "logs": [line.rstrip() for line in recent_lines],
                "count": len(recent_lines)
            }
    except Exception as e:
        return {
            "logs": [f"Error reading log file: {e}"],
            "count": 1
        }