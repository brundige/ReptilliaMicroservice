# domain/ports.py

"""
Ports (interfaces) for the reptile habitat automation system.

Ports define the contracts between the domain and external systems.
They specify WHAT the domain needs and HOW to interact with it,
but NOT the implementation details.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime

from domain.models import (
    SensorReading,
    SensorMetadata,
    OutletState,
    OutletCommand,
    Threshold,
    HabitatRequirements,
    Habitat,
    Alert,
    ReptileSpecies
)


# ═══════════════════════════════════════════════════════════════════
# SENSOR PORTS
# ═══════════════════════════════════════════════════════════════════

class SensorHardwareInterface(ABC):
    """
    Port for reading from physical sensors.

    Adapters: BluetoothSensor, DHT22Sensor, MockSensor, etc.
    """

    @abstractmethod
    def read_temperature_and_humidity(self) -> tuple[float, float]:
        """
        Read both temperature and humidity from sensor.

        Returns:
            Tuple of (temperature_celsius, humidity_percent)
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Check if sensor is responding correctly"""
        pass

    @abstractmethod
    def get_metadata(self) -> SensorMetadata:
        """Get sensor information (type, location, etc.)"""
        pass


class SensorRepository(ABC):
    """
    Port for storing and retrieving sensor readings.

    Adapters: PostgresRepository, InfluxDBRepository, InMemoryRepository
    """

    @abstractmethod
    def save_reading(self, reading: SensorReading) -> bool:
        """
        Persist a sensor reading.

        Args:
            reading: SensorReading object to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_readings(
            self,
            sensor_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[SensorReading]:
        """
        Retrieve historical readings for a sensor.

        Args:
            sensor_id: Sensor to get readings for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of SensorReading objects
        """
        pass

    @abstractmethod
    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """
        Get the most recent reading for a sensor.

        Args:
            sensor_id: Sensor to get reading for

        Returns:
            SensorReading or None if no readings exist
        """
        pass

    @abstractmethod
    def get_readings_by_habitat(
            self,
            habitat_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[SensorReading]:
        """
        Get all sensor readings for a habitat.

        Args:
            habitat_id: Habitat to get readings for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of all sensor readings for the habitat
        """
        pass


# ═══════════════════════════════════════════════════════════════════
# OUTLET/POWER CONTROL PORTS
# ═══════════════════════════════════════════════════════════════════

class OutletController(ABC):
    """
    Port for controlling power outlets.

    Adapters: KasaSmartStrip, GPIORelay, TPLinkPlug, MockOutlet
    """

    @abstractmethod
    def turn_on(self, outlet_id: str) -> bool:
        """
        Turn on an outlet.

        Args:
            outlet_id: Which outlet to turn on

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def turn_off(self, outlet_id: str) -> bool:
        """
        Turn off an outlet.

        Args:
            outlet_id: Which outlet to turn off

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_state(self, outlet_id: str) -> OutletState:
        """
        Get current state of outlet.

        Args:
            outlet_id: Which outlet to check

        Returns:
            OutletState object with current state
        """
        pass

    @abstractmethod
    def toggle(self, outlet_id: str) -> OutletState:
        """
        Toggle outlet state (ON → OFF or OFF → ON).

        Args:
            outlet_id: Which outlet to toggle

        Returns:
            OutletState object with new state
        """
        pass


class OutletRepository(ABC):
    """
    Port for storing outlet commands and state history.

    Adapters: PostgresOutletRepo, InMemoryOutletRepo
    """

    @abstractmethod
    def save_command(self, command: OutletCommand) -> bool:
        """
        Save outlet command for audit trail.

        Args:
            command: OutletCommand to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_command_history(
            self,
            outlet_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[OutletCommand]:
        """
        Get command history for an outlet.

        Args:
            outlet_id: Outlet to get history for
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of OutletCommand objects
        """
        pass

    @abstractmethod
    def get_current_state(self, outlet_id: str) -> Optional[OutletState]:
        """
        Get last known state from database.

        Args:
            outlet_id: Outlet to check

        Returns:
            OutletState or None
        """
        pass


# ═══════════════════════════════════════════════════════════════════
# HABITAT/CONFIGURATION PORTS
# ═══════════════════════════════════════════════════════════════════

class HabitatRepository(ABC):
    """
    Port for loading habitat configurations and species requirements.

    Adapters: PostgresHabitatRepo, JSONConfigRepo, InMemoryHabitatRepo
    """

    @abstractmethod
    def get_requirements(self, species: ReptileSpecies) -> HabitatRequirements:
        """
        Load ideal conditions for a reptile species from database.

        Args:
            species: ReptileSpecies enum value

        Returns:
            HabitatRequirements object with ideal conditions
        """
        pass

    @abstractmethod
    def get_habitat(self, habitat_id: str) -> Optional[Habitat]:
        """
        Load a specific habitat configuration.

        Args:
            habitat_id: Unique identifier for habitat

        Returns:
            Habitat object or None if not found
        """
        pass

    @abstractmethod
    def save_habitat(self, habitat: Habitat) -> bool:
        """
        Save habitat configuration.

        Args:
            habitat: Habitat object to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def list_habitats(self) -> List[Habitat]:
        """
        Get all configured habitats.

        Returns:
            List of all Habitat objects
        """
        pass


class ThresholdRepository(ABC):
    """
    Port for managing threshold configurations.

    Adapters: PostgresThresholdRepo, JSONThresholdRepo, InMemoryThresholdRepo
    """

    @abstractmethod
    def get_threshold(self, sensor_id: str) -> Optional[Threshold]:
        """
        Get threshold configuration for a sensor.

        Args:
            sensor_id: Sensor to get threshold for

        Returns:
            Threshold object or None
        """
        pass

    @abstractmethod
    def save_threshold(self, threshold: Threshold) -> bool:
        """
        Save threshold configuration.

        Args:
            threshold: Threshold object to save

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_thresholds_by_habitat(self, habitat_id: str) -> List[Threshold]:
        """
        Get all thresholds for a habitat.

        Args:
            habitat_id: Habitat to get thresholds for

        Returns:
            List of Threshold objects
        """
        pass


# ═══════════════════════════════════════════════════════════════════
# NOTIFICATION/ALERTING PORTS
# ═══════════════════════════════════════════════════════════════════

class NotificationService(ABC):
    """
    Port for sending alerts and notifications.

    Adapters: MQTTNotifier, EmailNotifier, PushNotifier, ConsoleNotifier
    """

    @abstractmethod
    def send_alert(self, alert: Alert) -> bool:
        """
        Send an alert notification.

        Args:
            alert: Alert object to send

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @abstractmethod
    def send_status_update(self, habitat_id: str, status: dict) -> bool:
        """
        Send routine status update.

        Args:
            habitat_id: Habitat to send status for
            status: Status information as dict

        Returns:
            True if sent successfully, False otherwise
        """
        pass


# ═══════════════════════════════════════════════════════════════════
# INFRASTRUCTURE/UTILITY PORTS
# ═══════════════════════════════════════════════════════════════════

class TimeProvider(ABC):
    """
    Port for getting current time.

    Adapters: SystemTimeProvider, FixedTimeProvider (for testing)

    This is useful for testing - you can control time!
    """

    @abstractmethod
    def now(self) -> datetime:
        """
        Get current timestamp.

        Returns:
            Current datetime
        """
        pass


class SunTimesProvider(ABC):
    """
    Port for getting sunrise/sunset times.

    Adapters: AstralSunTimesProvider (uses astronomical calculations),
              FixedSunTimesProvider (for testing)

    This enables time-based lighting schedules tied to natural daylight cycles.
    """

    @abstractmethod
    def get_sunrise(self, date: datetime = None) -> datetime:
        """
        Get sunrise time for the given date.

        Args:
            date: Date to get sunrise for (defaults to today)

        Returns:
            datetime of sunrise
        """
        pass

    @abstractmethod
    def get_sunset(self, date: datetime = None) -> datetime:
        """
        Get sunset time for the given date.

        Args:
            date: Date to get sunset for (defaults to today)

        Returns:
            datetime of sunset
        """
        pass

    @abstractmethod
    def is_daytime(self, current_time: datetime = None) -> bool:
        """
        Check if it's currently daytime (between sunrise and sunset).

        Args:
            current_time: Time to check (defaults to now)

        Returns:
            True if daytime, False if nighttime
        """
        pass


class Logger(ABC):
    """
    Port for logging.

    Adapters: StdoutLogger, FileLogger, CloudLogger, MemoryLogger (testing)
    """

    @abstractmethod
    def info(self, message: str, context: dict = None) -> None:
        """
        Log informational message.

        Args:
            message: Message to log
            context: Optional dict with additional context
        """
        pass

    @abstractmethod
    def warning(self, message: str, context: dict = None) -> None:
        """
        Log warning.

        Args:
            message: Warning message
            context: Optional dict with additional context
        """
        pass

    @abstractmethod
    def error(
            self,
            message: str,
            context: dict = None,
            exception: Exception = None
    ) -> None:
        """
        Log error.

        Args:
            message: Error message
            context: Optional dict with additional context
            exception: Optional exception object
        """
        pass

    @abstractmethod
    def debug(self, message: str, context: dict = None) -> None:
        """
        Log debug information.

        Args:
            message: Debug message
            context: Optional dict with additional context
        """
        pass