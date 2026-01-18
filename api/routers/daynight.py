# api/routers/daynight.py

"""
Day/Night control endpoints for the Reptilia API.
"""

from datetime import datetime, timezone, date
from typing import Optional
from fastapi import APIRouter, Depends, Query
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    DayNightStatusResponse,
    SunTimesResponse,
    ForceModeRequest
)
from api.models.enums import DayNightMode

router = APIRouter(prefix="/daynight", tags=["Day/Night"])


# Default sun times (can be configured or calculated with astral library)
DEFAULT_SUNRISE_HOUR = 7
DEFAULT_SUNRISE_MINUTE = 0
DEFAULT_SUNSET_HOUR = 19
DEFAULT_SUNSET_MINUTE = 0


@router.get("/status", response_model=DayNightStatusResponse)
def get_daynight_status(db: Database = Depends(get_db)):
    """Get current day/night status."""
    now = datetime.now(timezone.utc)
    today = now.date()

    # Get or calculate sun times
    sunrise = datetime(
        today.year, today.month, today.day,
        DEFAULT_SUNRISE_HOUR, DEFAULT_SUNRISE_MINUTE,
        tzinfo=timezone.utc
    )
    sunset = datetime(
        today.year, today.month, today.day,
        DEFAULT_SUNSET_HOUR, DEFAULT_SUNSET_MINUTE,
        tzinfo=timezone.utc
    )

    # Check for forced mode in database
    config = db.daynight_config.find_one({"_id": "current"})
    if config and config.get("forced_mode"):
        is_day = config["forced_mode"] == "day"
        mode = DayNightMode.DAY if is_day else DayNightMode.NIGHT
    else:
        # Calculate based on sun times
        is_day = sunrise <= now <= sunset
        mode = DayNightMode.DAY if is_day else DayNightMode.NIGHT

    # Get registered habitats
    habitats = list(db.habitats.find({}, {"habitat_id": 1}))
    habitat_ids = [h["habitat_id"] for h in habitats]

    return DayNightStatusResponse(
        mode=mode,
        is_day_mode=is_day,
        last_mode_change=config.get("last_mode_change") if config else None,
        sunrise=sunrise,
        sunset=sunset,
        current_time=now,
        registered_habitats=habitat_ids
    )


@router.get("/sun-times", response_model=SunTimesResponse)
def get_sun_times(
    date_str: Optional[str] = Query(default=None, alias="date"),
    db: Database = Depends(get_db)
):
    """Get sunrise and sunset times."""
    if date_str:
        try:
            query_date = date.fromisoformat(date_str)
        except ValueError:
            query_date = date.today()
    else:
        query_date = date.today()

    sunrise = datetime(
        query_date.year, query_date.month, query_date.day,
        DEFAULT_SUNRISE_HOUR, DEFAULT_SUNRISE_MINUTE,
        tzinfo=timezone.utc
    )
    sunset = datetime(
        query_date.year, query_date.month, query_date.day,
        DEFAULT_SUNSET_HOUR, DEFAULT_SUNSET_MINUTE,
        tzinfo=timezone.utc
    )

    now = datetime.now(timezone.utc)
    is_daytime = sunrise <= now <= sunset

    return SunTimesResponse(
        date=query_date.isoformat(),
        sunrise=sunrise,
        sunset=sunset,
        is_daytime=is_daytime
    )


@router.post("/force-mode", response_model=DayNightStatusResponse)
def force_mode(request: ForceModeRequest, db: Database = Depends(get_db)):
    """Force day or night mode (for testing/override)."""
    now = datetime.now(timezone.utc)

    db.daynight_config.update_one(
        {"_id": "current"},
        {"$set": {
            "forced_mode": request.mode.value,
            "last_mode_change": now
        }},
        upsert=True
    )

    # Return updated status
    return get_daynight_status(db)


@router.post("/auto-mode", response_model=DayNightStatusResponse)
def auto_mode(db: Database = Depends(get_db)):
    """Clear forced mode and return to automatic sun-based control."""
    now = datetime.now(timezone.utc)

    db.daynight_config.update_one(
        {"_id": "current"},
        {"$set": {
            "forced_mode": None,
            "last_mode_change": now
        }},
        upsert=True
    )

    return get_daynight_status(db)
