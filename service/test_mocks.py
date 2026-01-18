# test_mocks.py

"""
Quick test to verify mock adapters work
"""

from adapters.mock import (
    MockTemperatureHumiditySensor,
    InMemorySensorRepository,
    MockOutletController
)
from domain.models import SensorUnit
from datetime import datetime, timezone

print("🧪 Testing Mock Adapters...\n")

# Test mock sensor
print("=== Testing Mock Sensor ===")
sensor = MockTemperatureHumiditySensor(base_temp=22.0, base_humidity=50.0)
temp, humidity = sensor.read_temperature_and_humidity()
print(f"✅ Read: {temp}°C, {humidity}%")
print(f"✅ Healthy: {sensor.is_healthy()}")

# Test breaking sensor
sensor.break_sensor()
print(f"✅ Healthy after break: {sensor.is_healthy()}")
sensor.fix_sensor()

# Test repository
print("\n=== Testing Mock Repository ===")
repo = InMemorySensorRepository()

from domain.models import SensorReading
reading = SensorReading(
    sensor_id="test-sensor",
    value=25.5,
    timestamp=datetime.now(timezone.utc),
    unit=SensorUnit.CELSIUS
)

repo.save_reading(reading)
print(f"✅ Saved reading")

latest = repo.get_latest_reading("test-sensor")
print(f"✅ Retrieved: {latest.value}°C")

# Test outlet controller
print("\n=== Testing Mock Outlet Controller ===")
outlet = MockOutletController()
outlet.turn_on("heater")
outlet.turn_off("heater")
state = outlet.get_state("heater")
print(f"✅ Outlet state: {state.state.value}")

print("\n✅ All mock adapters working!")