# adapters/mock/mock_repositories.py

"""
Mock repository adapters - store everything in memory (Python lists/dicts).
No database needed!
"""

from typing import List, Optional, Dict
from datetime import datetime

from domain.ports import (
    SensorRepository,
    OutletRepository,
    HabitatRepository,
    ThresholdRepository
)
from domain.models import (
    SensorReading,
    OutletCommand,
    OutletState,
    Habitat,
    HabitatRequirements,
    ReptileSpecies,
    Threshold
)


class InMemorySensorRepository(SensorRepository):
    """
    Store sensor readings in memory (Python list).
    All data is lost when program stops - perfect for testing!
    """

    def __init__(self):
        self._readings: List[SensorReading] = []
        print("📦 InMemorySensorRepository created")

    def save_reading(self, reading: SensorReading) -> bool:
        """Save to list"""
        self._readings.append(reading)
        return True

    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get most recent reading for sensor"""
        sensor_readings = [
            r for r in self._readings
            if r.sensor_id == sensor_id
        ]

        if not sensor_readings:
            return None

        # Return most recent by timestamp
        return max(sensor_readings, key=lambda r: r.timestamp)

    def get_readings(
            self,
            sensor_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[SensorReading]:
        """Get readings in time range"""
        return [
            r for r in self._readings
            if r.sensor_id == sensor_id
               and start_time <= r.timestamp <= end_time
        ]

    def get_readings_by_habitat(
            self,
            habitat_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[SensorReading]:
        """Get all readings for habitat (simplified - just return all)"""
        return [
            r for r in self._readings
            if start_time <= r.timestamp <= end_time
        ]

    def clear(self):
        """Clear all data (useful for tests)"""
        self._readings = []
        print("🗑️  Sensor readings cleared")

    def count(self) -> int:
        """Get total number of readings stored"""
        return len(self._readings)


class InMemoryOutletRepository(OutletRepository):
    """Store outlet commands in memory"""

    def __init__(self):
        self._commands: List[OutletCommand] = []
        self._states: Dict[str, OutletState] = {}
        print("📦 InMemoryOutletRepository created")

    def save_command(self, command: OutletCommand) -> bool:
        """Save command to history"""
        self._commands.append(command)
        return True

    def get_command_history(
            self,
            outlet_id: str,
            start_time: datetime,
            end_time: datetime
    ) -> List[OutletCommand]:
        """Get command history for outlet"""
        return [
            c for c in self._commands
            if c.outlet_id == outlet_id
               and start_time <= c.timestamp <= end_time
        ]

    def get_current_state(self, outlet_id: str) -> Optional[OutletState]:
        """Get last known state"""
        return self._states.get(outlet_id)

    def save_state(self, state: OutletState):
        """Update current state"""
        self._states[outlet_id] = state

    def clear(self):
        """Clear all data"""
        self._commands = []
        self._states = {}
        print("🗑️  Outlet commands cleared")


class InMemoryHabitatRepository(HabitatRepository):
    """Store habitat configurations in memory"""

    def __init__(self):
        self._habitats: Dict[str, Habitat] = {}

        # Pre-load species requirements (hardcoded)
        self._requirements = {
            ReptileSpecies.BEARDED_DRAGON: HabitatRequirements(
                species=ReptileSpecies.BEARDED_DRAGON,
                basking_temp_min=35.0,
                basking_temp_max=40.0,
                cool_side_temp_min=24.0,
                cool_side_temp_max=29.0,
                night_temp_min=20.0,
                night_temp_max=24.0,
                humidity_min=30.0,
                humidity_max=40.0,
                uv_required=True,
                substrate_type="tile or paper",
                notes="Desert species, needs hot basking spot"
            ),
            ReptileSpecies.BALL_PYTHON: HabitatRequirements(
                species=ReptileSpecies.BALL_PYTHON,
                basking_temp_min=31.0,
                basking_temp_max=33.0,
                cool_side_temp_min=26.0,
                cool_side_temp_max=28.0,
                night_temp_min=24.0,
                night_temp_max=26.0,
                humidity_min=50.0,
                humidity_max=60.0,
                uv_required=False,
                substrate_type="cypress mulch",
                notes="Tropical species, needs higher humidity"
            ),
            ReptileSpecies.CORN_SNAKE: HabitatRequirements(
                species=ReptileSpecies.CORN_SNAKE,
                basking_temp_min=28.0,
                basking_temp_max=32.0,
                cool_side_temp_min=21.0,
                cool_side_temp_max=24.0,
                night_temp_min=20.0,
                night_temp_max=23.0,
                humidity_min=40.0,
                humidity_max=50.0,
                uv_required=False,
                substrate_type="aspen shavings",
                notes="Hardy species, moderate temps"
            ),
            ReptileSpecies.LEOPARD_GECKO: HabitatRequirements(
                species=ReptileSpecies.LEOPARD_GECKO,
                basking_temp_min=32.0,
                basking_temp_max=35.0,
                cool_side_temp_min=24.0,
                cool_side_temp_max=27.0,
                night_temp_min=21.0,
                night_temp_max=24.0,
                humidity_min=30.0,
                humidity_max=40.0,
                uv_required=False,
                substrate_type="tile or paper",
                notes="Desert species, use heat mat for belly heat"
            )
        }

        print("📦 InMemoryHabitatRepository created with species data")

    def get_requirements(self, species: ReptileSpecies) -> HabitatRequirements:
        """Load species requirements"""
        if species not in self._requirements:
            raise ValueError(f"No requirements found for {species.value}")
        return self._requirements[species]

    def get_habitat(self, habitat_id: str) -> Optional[Habitat]:
        """Load habitat by ID"""
        return self._habitats.get(habitat_id)

    def save_habitat(self, habitat: Habitat) -> bool:
        """Save habitat configuration"""
        self._habitats[habitat.habitat_id] = habitat
        print(f"💾 Saved habitat: {habitat.name}")
        return True

    def list_habitats(self) -> List[Habitat]:
        """Get all habitats"""
        return list(self._habitats.values())

    def clear(self):
        """Clear all habitats (keeps species requirements)"""
        self._habitats = {}
        print("🗑️  Habitats cleared")


class InMemoryThresholdRepository(ThresholdRepository):
    """Store thresholds in memory"""

    def __init__(self):
        self._thresholds: Dict[str, Threshold] = {}
        print("📦 InMemoryThresholdRepository created")

    def get_threshold(self, sensor_id: str) -> Optional[Threshold]:
        """Get threshold for sensor"""
        return self._thresholds.get(sensor_id)

    def save_threshold(self, threshold: Threshold) -> bool:
        """Save threshold"""
        self._thresholds[threshold.sensor_id] = threshold
        print(f"💾 Saved threshold for {threshold.sensor_id}: {threshold.min_value}-{threshold.max_value}")
        return True

    def get_thresholds_by_habitat(self, habitat_id: str) -> List[Threshold]:
        """Get all thresholds for habitat (simplified)"""
        return list(self._thresholds.values())

    def clear(self):
        """Clear all thresholds"""
        self._thresholds = {}
        print("🗑️  Thresholds cleared")