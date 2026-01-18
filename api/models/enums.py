# api/models/enums.py

"""
Enums for the Reptilia API.
"""

from enum import Enum


class ReptileSpecies(str, Enum):
    BALL_PYTHON = "ball_python"
    CORN_SNAKE = "corn_snake"
    BEARDED_DRAGON = "bearded_dragon"
    LEOPARD_GECKO = "leopard_gecko"


class SensorUnit(str, Enum):
    CELSIUS = "°C"
    FAHRENHEIT = "°F"
    PERCENT = "%"


class OutletState(str, Enum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    ERROR = "error"


class ControlMode(str, Enum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"
    OVERRIDE = "override"


class AlertSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class SensorStatus(str, Enum):
    ACTIVE = "active"
    STALE = "stale"
    NO_DATA = "no_data"


class ThresholdStatus(str, Enum):
    OK = "ok"
    TOO_LOW = "too_low"
    TOO_HIGH = "too_high"
    UNKNOWN = "unknown"


class DayNightMode(str, Enum):
    DAY = "day"
    NIGHT = "night"


class SystemHealth(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class TriggerOperator(str, Enum):
    LT = "lt"
    GT = "gt"
    LTE = "lte"
    GTE = "gte"
    EQ = "eq"
