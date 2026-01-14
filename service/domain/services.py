# Monitor Sensor readings and Save them
from domain.models import SensorUnit, SensorReading
from domain.ports import SensorRepositoryInterface, TimeProvider


class SensorMonitoringService:
    '''
    Service for processing sensor readings.

    '''

    def __init__(self, sensor_repository: SensorRepositoryInterface, time_provider: TimeProvider):
        self.sensor_repository = sensor_repository
        self.time_provider = time_provider

        def process_reading(self, sensor_id: str, value: float, timestamp=None) -> SensorReading:

            # create domain model
            reading = SensorReading(sensor_id=sensor_id, value=value, timestamp=timestamp, unit=SensorUnit.FAHRENHEIT,
                                    is_valid=self.validate_reading(value))

            # validate the reading
            if not self._is_valid_reading(reading):
                reading.is_valid = False
                print(f"Invalid reading for sensor {sensor_id}: {value}")
                return reading

            # save using the repository port
            saved = self.sensor_repository.save_sensor_data(reading)
            if not saved:
                print(f"Failed to save reading for sensor {sensor_id}")
                return None

            return reading
        
        def _is_valid_reading(self, reading: SensorReading) -> bool:
            # Implement validation logic here, e.g., check if value is within expected range
            if reading.value < -40 or reading.value > 125:  # Example range for temperature in Fahrenheit
                return False
            return True

# Control outlets based on automation rules
# setup new habitat with proper thresholds
