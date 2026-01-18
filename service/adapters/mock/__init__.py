# adapters/mock/__init__.py

"""
Mock adapters for testing without real hardware.
"""

from .mock_sensor import MockTemperatureHumiditySensor
from .mock_repositories import (
    InMemorySensorRepository,
    InMemoryOutletRepository,
    InMemoryHabitatRepository,
    InMemoryThresholdRepository
)
from .mock_outlet import MockOutletController

__all__ = [
    'MockTemperatureHumiditySensor',
    'InMemorySensorRepository',
    'InMemoryOutletRepository',
    'InMemoryHabitatRepository',
    'InMemoryThresholdRepository',
    'MockOutletController'
]