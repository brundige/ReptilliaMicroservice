# ports.py
import datetime
from abc import ABC, abstractmethod
from datetime import datetime, timedelta


class SensorHardwareInterface(ABC):
    @abstractmethod
    def read_sensor_data(self):
        pass


# Sensor Repository -- stores the data from the sensor, could be a database or in-memory storage
class SensorRepositoryInterface(ABC):
    @abstractmethod
    def save_sensor_data(self, data):
        pass

    @abstractmethod
    def get_sensor_data(self):
        pass


# Outlet
class OutletHardwareInterface(ABC):
    @abstractmethod
    def turn_on(self):
        pass

    @abstractmethod
    def turn_off(self):
        pass


# Gets Ideal Habitat Requirements
class HabitatRepository(ABC):
    @abstractmethod
    def get_requirements(self):
        pass


# time provider --  provides current time, could be used for scheduling or logging
class TimeProvider(ABC):
    @abstractmethod
    def now(self) -> datetime:
        pass


# Adapter for production - uses real time
class SystemTimeProvider(TimeProvider):
    def now(self) -> datetime:
        return datetime.datetime.now()


# Adapter for testing - YOU control the time!
class FixedTimeProvider(TimeProvider):
    def __init__(self, fixed_time: datetime):
        self._current_time = fixed_time

    def now(self) -> datetime:
        return self._current_time

    def advance(self, minutes: int):
        """Move time forward for testing"""
        self._current_time += datetime.timedelta(minutes=minutes)



