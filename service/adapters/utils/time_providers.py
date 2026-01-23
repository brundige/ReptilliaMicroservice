# adapters/utils/time_providers.py

"""
Time provider adapters - for getting current time and sun times
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from domain.ports import TimeProvider, SunTimesProvider

# Import astral with graceful fallback
try:
    from astral import LocationInfo
    from astral.sun import sun
    ASTRAL_AVAILABLE = True
except ImportError:
    ASTRAL_AVAILABLE = False


class SystemTimeProvider(TimeProvider):
    """Production time provider - uses real system time"""

    def now(self) -> datetime:
        """Get current system time as timezone-aware UTC datetime"""
        return datetime.now(timezone.utc)


class FixedTimeProvider(TimeProvider):
    """Testing time provider - YOU control the time!"""

    def __init__(self, fixed_time: datetime):
        """
        Args:
            fixed_time: The time to return from now()
        """
        self._current_time = fixed_time

    def now(self) -> datetime:
        """Get the fixed time"""
        return self._current_time

    def advance(self, minutes: int):
        """
        Move time forward for testing.

        Args:
            minutes: How many minutes to advance
        """
        self._current_time += timedelta(minutes=minutes)

    def set_time(self, new_time: datetime):
        """
        Set time to specific value.

        Args:
            new_time: Time to set
        """
        self._current_time = new_time


# ═══════════════════════════════════════════════════════════════════
# SUN TIMES PROVIDERS
# ═══════════════════════════════════════════════════════════════════

class AstralSunTimesProvider(SunTimesProvider):
    """
    Production sun times provider using astronomical calculations.

    Uses the 'astral' library to calculate accurate sunrise/sunset times
    based on geographic location.

    Requires: pip install astral
    """

    def __init__(
        self,
        latitude: float,
        longitude: float,
        timezone_name: str = "UTC",
        location_name: str = "Habitat Location"
    ):
        """
        Initialize with geographic coordinates.

        Args:
            latitude: Latitude in decimal degrees (positive = North)
            longitude: Longitude in decimal degrees (positive = East)
            timezone_name: Timezone name (e.g., "America/New_York", "UTC")
            location_name: Human-readable name for the location
        """
        if not ASTRAL_AVAILABLE:
            raise ImportError(
                "astral library not installed. Run: pip install astral"
            )

        self._location = LocationInfo(
            name=location_name,
            region="",
            timezone=timezone_name,
            latitude=latitude,
            longitude=longitude
        )
        self._timezone_name = timezone_name

    def get_sunrise(self, date: datetime = None) -> datetime:
        """Get sunrise time for the given date."""
        if date is None:
            date = datetime.now(timezone.utc)

        s = sun(self._location.observer, date=date.date())
        return s["sunrise"]

    def get_sunset(self, date: datetime = None) -> datetime:
        """Get sunset time for the given date."""
        if date is None:
            date = datetime.now(timezone.utc)

        s = sun(self._location.observer, date=date.date())
        return s["sunset"]

    def is_daytime(self, current_time: datetime = None) -> bool:
        """Check if it's currently daytime (between sunrise and sunset)."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        # Ensure current_time is timezone-aware
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        sunrise = self.get_sunrise(current_time)
        sunset = self.get_sunset(current_time)

        return sunrise <= current_time < sunset

    @property
    def location(self) -> LocationInfo:
        """Get the location info."""
        return self._location


class FixedSunTimesProvider(SunTimesProvider):
    """
    Testing sun times provider - YOU control sunrise/sunset!

    Useful for testing day/night transitions without waiting for actual
    sunrise/sunset times.
    """

    def __init__(
        self,
        sunrise_hour: int = 7,
        sunrise_minute: int = 0,
        sunset_hour: int = 19,
        sunset_minute: int = 0
    ):
        """
        Initialize with fixed sunrise/sunset times.

        Args:
            sunrise_hour: Hour of sunrise (0-23)
            sunrise_minute: Minute of sunrise (0-59)
            sunset_hour: Hour of sunset (0-23)
            sunset_minute: Minute of sunset (0-59)
        """
        self._sunrise_hour = sunrise_hour
        self._sunrise_minute = sunrise_minute
        self._sunset_hour = sunset_hour
        self._sunset_minute = sunset_minute

    def get_sunrise(self, date: datetime = None) -> datetime:
        """Get sunrise time for the given date."""
        if date is None:
            date = datetime.now(timezone.utc)

        return date.replace(
            hour=self._sunrise_hour,
            minute=self._sunrise_minute,
            second=0,
            microsecond=0
        )

    def get_sunset(self, date: datetime = None) -> datetime:
        """Get sunset time for the given date."""
        if date is None:
            date = datetime.now(timezone.utc)

        return date.replace(
            hour=self._sunset_hour,
            minute=self._sunset_minute,
            second=0,
            microsecond=0
        )

    def is_daytime(self, current_time: datetime = None) -> bool:
        """Check if it's currently daytime (between sunrise and sunset)."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)

        sunrise = self.get_sunrise(current_time)
        sunset = self.get_sunset(current_time)

        return sunrise <= current_time < sunset

    def set_sunrise(self, hour: int, minute: int = 0):
        """Update sunrise time for testing."""
        self._sunrise_hour = hour
        self._sunrise_minute = minute

    def set_sunset(self, hour: int, minute: int = 0):
        """Update sunset time for testing."""
        self._sunset_hour = hour
        self._sunset_minute = minute