# adapters/mock/mock_sensor.py

"""
Mock sensor adapter for testing without real hardware.
Returns random temperature and humidity values.
"""

import random
from domain.ports import SensorHardwareInterface
from domain.models import SensorMetadata, SensorType, SensorUnit


class MockTemperatureHumiditySensor(SensorHardwareInterface):
    """
    Fake sensor that generates random values.
    Perfect for testing the entire system without hardware!
    """

    def __init__(
            self,
            base_temp: float = 25.0,
            base_humidity: float = 50.0,
            variation: float = 3.0,
            name: str = "Mock Sensor"
    ):
        """
        Args:
            base_temp: Average temperature to return
            base_humidity: Average humidity to return
            variation: How much to vary from base (±variation)
            name: Sensor name for metadata
        """
        self._base_temp = base_temp
        self._base_humidity = base_humidity
        self._variation = variation
        self._name = name
        self._is_healthy = True
        self._read_count = 0

    def read_temperature_and_humidity(self) -> tuple[float, float]:
        """
        Return fake random values.
        Simulates real sensor readings.
        """
        if not self._is_healthy:
            raise IOError("Sensor is broken (simulated failure)")

        # Generate random values around base with variation
        temp = self._base_temp + random.uniform(-self._variation, self._variation)
        humidity = self._base_humidity + random.uniform(-self._variation, self._variation)

        # Keep humidity in valid range (0-100%)
        humidity = max(0.0, min(100.0, humidity))

        self._read_count += 1

        # Simulate occasional drift
        if self._read_count % 10 == 0:
            self._base_temp += random.uniform(-0.5, 0.5)
            self._base_humidity += random.uniform(-2, 2)

        return (round(temp, 1), round(humidity, 1))

    def is_healthy(self) -> bool:
        """Check if sensor is working"""
        return self._is_healthy

    def get_metadata(self) -> SensorMetadata:
        """Return sensor metadata"""
        return SensorMetadata(
            sensor_id="mock-sensor",
            sensor_type=SensorType.TEMPERATURE,
            unit=SensorUnit.CELSIUS,
            location=self._name,
            manufacturer="Mock Industries",
            model="MOCK-2000",
            min_value=-50.0,
            max_value=100.0,
            accuracy=0.1
        )

    # ===== Testing helpers =====

    def break_sensor(self):
        """Simulate sensor failure (for testing error handling)"""
        self._is_healthy = False
        print("💥 Mock sensor broken!")

    def fix_sensor(self):
        """Restore sensor (for testing recovery)"""
        self._is_healthy = True
        print("🔧 Mock sensor fixed!")

    def set_temperature(self, temp: float):
        """Manually set temperature (for testing specific scenarios)"""
        self._base_temp = temp

    def set_humidity(self, humidity: float):
        """Manually set humidity (for testing specific scenarios)"""
        self._base_humidity = humidity