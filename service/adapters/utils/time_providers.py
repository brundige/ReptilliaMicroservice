"""
Time provider adapters for the Reptilia habitat automation system.

These adapters implement the TimeProvider and SunTimesProvider ports
for getting current time and sunrise/sunset calculations.

All times are handled in UTC for consistency.
"""

from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from astral import LocationInfo
from astral.sun import sun

from domain.ports import TimeProvider, SunTimesProvider


class SystemTimeProvider(TimeProvider):
    """
    Real system time provider.

    Uses the actual system clock, returns UTC time.
    """

    def now(self) -> datetime:
        """Get current system time in UTC."""
        return datetime.now(timezone.utc)


class FixedTimeProvider(TimeProvider):
    """
    Fixed time provider for testing.

    Returns a configurable fixed time in UTC, useful for deterministic tests.
    """

    def __init__(self, fixed_time: datetime):
        """
        Initialize with a fixed time.

        Args:
            fixed_time: The datetime to always return (will be converted to UTC)
        """
        if fixed_time.tzinfo is None:
            fixed_time = fixed_time.replace(tzinfo=timezone.utc)
        else:
            fixed_time = fixed_time.astimezone(timezone.utc)
        self._fixed_time = fixed_time

    def now(self) -> datetime:
        """Get the fixed time in UTC."""
        return self._fixed_time

    def set_time(self, new_time: datetime) -> None:
        """
        Update the fixed time.

        Args:
            new_time: New datetime to return (will be converted to UTC)
        """
        if new_time.tzinfo is None:
            new_time = new_time.replace(tzinfo=timezone.utc)
        else:
            new_time = new_time.astimezone(timezone.utc)
        self._fixed_time = new_time


class AstralSunTimesProvider(SunTimesProvider):
    """
    Sun times provider using the Astral library.

    Calculates accurate sunrise/sunset times based on geographic coordinates
    using astronomical calculations. All times returned in UTC.
    """

    def __init__(
        self,
        latitude: float,
        longitude: float,
        timezone_name: str = "UTC",
        location_name: str = "Location"
    ):
        """
        Initialize with geographic coordinates.

        Args:
            latitude: Latitude in decimal degrees (positive = North)
            longitude: Longitude in decimal degrees (positive = East)
            timezone_name: Timezone name (e.g., "America/New_York")
            location_name: Human-readable location name
        """
        self._latitude = latitude
        self._longitude = longitude
        self._timezone_name = timezone_name
        self._tz = ZoneInfo(timezone_name)
        self._location = LocationInfo(
            name=location_name,
            region="",
            timezone=timezone_name,
            latitude=latitude,
            longitude=longitude
        )

    def _get_sun_times(self, date: Optional[datetime] = None) -> dict:
        """
        Get sun times for a given date.

        Args:
            date: Date to calculate for (defaults to today in UTC)

        Returns:
            Dictionary with sunrise, sunset, etc. (all in UTC)
        """
        if date is None:
            date = datetime.now(timezone.utc)
        return sun(self._location.observer, date=date.date(), tzinfo=timezone.utc)

    def get_sunrise(self, date: Optional[datetime] = None) -> datetime:
        """
        Get sunrise time for the given date.

        Args:
            date: Date to get sunrise for (defaults to today)

        Returns:
            datetime of sunrise in UTC
        """
        sun_times = self._get_sun_times(date)
        return sun_times["sunrise"].astimezone(timezone.utc)

    def get_sunset(self, date: Optional[datetime] = None) -> datetime:
        """
        Get sunset time for the given date.

        Args:
            date: Date to get sunset for (defaults to today)

        Returns:
            datetime of sunset in UTC
        """
        sun_times = self._get_sun_times(date)
        return sun_times["sunset"].astimezone(timezone.utc)

    def is_daytime(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if it's currently daytime (between sunrise and sunset).

        Args:
            current_time: Time to check (defaults to now in UTC)

        Returns:
            True if daytime, False if nighttime
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)

        sunrise = self.get_sunrise(current_time)
        sunset = self.get_sunset(current_time)

        return sunrise <= current_time <= sunset


class FixedSunTimesProvider(SunTimesProvider):
    """
    Fixed sun times provider for testing.

    Returns configurable fixed sunrise/sunset times in UTC for deterministic tests.
    """

    def __init__(
        self,
        sunrise_hour: int = 6,
        sunrise_minute: int = 0,
        sunset_hour: int = 18,
        sunset_minute: int = 0
    ):
        """
        Initialize with fixed sunrise/sunset times (in UTC).

        Args:
            sunrise_hour: Hour of sunrise in UTC (0-23)
            sunrise_minute: Minute of sunrise (0-59)
            sunset_hour: Hour of sunset in UTC (0-23)
            sunset_minute: Minute of sunset (0-59)
        """
        self._sunrise_hour = sunrise_hour
        self._sunrise_minute = sunrise_minute
        self._sunset_hour = sunset_hour
        self._sunset_minute = sunset_minute

    def get_sunrise(self, date: Optional[datetime] = None) -> datetime:
        """
        Get fixed sunrise time for the given date.

        Args:
            date: Date to get sunrise for (defaults to today)

        Returns:
            datetime of sunrise in UTC
        """
        if date is None:
            date = datetime.now(timezone.utc)
        elif date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        else:
            date = date.astimezone(timezone.utc)

        return date.replace(
            hour=self._sunrise_hour,
            minute=self._sunrise_minute,
            second=0,
            microsecond=0
        )

    def get_sunset(self, date: Optional[datetime] = None) -> datetime:
        """
        Get fixed sunset time for the given date.

        Args:
            date: Date to get sunset for (defaults to today)

        Returns:
            datetime of sunset in UTC
        """
        if date is None:
            date = datetime.now(timezone.utc)
        elif date.tzinfo is None:
            date = date.replace(tzinfo=timezone.utc)
        else:
            date = date.astimezone(timezone.utc)

        return date.replace(
            hour=self._sunset_hour,
            minute=self._sunset_minute,
            second=0,
            microsecond=0
        )

    def is_daytime(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if it's currently daytime based on fixed times.

        Args:
            current_time: Time to check (defaults to now in UTC)

        Returns:
            True if daytime, False if nighttime
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        else:
            current_time = current_time.astimezone(timezone.utc)

        sunrise = self.get_sunrise(current_time)
        sunset = self.get_sunset(current_time)

        return sunrise <= current_time <= sunset
