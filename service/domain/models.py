from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, List


# ========== Enums for Sensor Types and Units ==========

class SensorType(Enum):
    TEMPERATURE = "temperature"
    HUMIDITY = "humidity"


class SensorUnit(Enum):
    CELSIUS = "*C"
    FAHRENHEIT = "*F"
    PERCENT = "%"


class OutletState(Enum):
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    ERROR = "error"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class ReptileSpecies(Enum):
    BALL_PYTHON = "ball_python"
    CORN_SNAKE = "corn_snake"
    BEARDED_DRAGON = "bearded_dragon"
    LEOPARD_GECKO = "leopard_gecko"


class ComparisonOperator(Enum):

    """Comparison operators for automation rules"""
    LESS_THAN = 'lt'
    GREATER_THAN = 'gt'
    LESS_THAN_OR_EQUAL = 'lte'
    GREATER_THAN_OR_EQUAL = 'gte'
    EQUAL = 'eq'


@dataclass
class SensorReading:
    sensor_id: str
    value: float
    timestamp: datetime
    unit: SensorUnit
    is_valid: bool = True


@dataclass
class HabitatRequirements:
    """
    Ideal conditions for a reptile species.
    This is what you load FROM the database.
    """
    species: ReptileSpecies

    # Temperature requirements
    basking_temp_min: float
    basking_temp_max: float
    cool_side_temp_min: float
    cool_side_temp_max: float
    night_temp_min: float
    night_temp_max: float

    # Humidity requirements
    humidity_min: float
    humidity_max: float

    # Optional
    uv_required: bool = False
    substrate_type: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Habitat:
    """
    A specific enclosure/terrarium.
    This represents ONE physical setup.
    """
    habitat_id: str
    name: str  # "Fred's Enclosure", "Quarantine Tank"
    species: ReptileSpecies
    requirements: HabitatRequirements  # ← Loaded from DB

    # Which sensors monitor this habitat
    basking_temp_sensor_id: str
    cool_temp_sensor_id: str
    humidity_sensor_id: str

    # Which outlets control this habitat
    heat_lamp_outlet_id: str
    ceramic_heater_outlet_id: Optional[str] = None  # For cool side/ambient heat
    uvb_outlet_id: Optional[str] = None
    humidifier_outlet_id: Optional[str] = None
    mister_outlet_id: Optional[str] = None


@dataclass
class Threshold:
    """
    Operational thresholds for a specific sensor.
    Generated FROM the HabitatRequirements, but can be overridden by the user.
    """
    sensor_id: str
    zone_type: str  # i.e "basking", "cool_side", "night", "humidity"

    # critical thresholds
    min_value: float
    max_value: float

    # warning thresholds (optional)
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None

    # Add hysteresis to prevent rapid toggling of outlets
    hysteresis: float = 2.0  # Default hysteresis value to prevent rapid toggling

    @classmethod
    def from_habitat_requirements(
            cls,
            sensor_id: str,
            zone_type: str,
            requirements: HabitatRequirements
    ) -> 'Threshold':
        """
        Create thresholds from species requirements.
        Business logic for converting requirements → operational thresholds.
        """
        if zone_type == "basking":
            return cls(
                sensor_id=sensor_id,
                zone_type=zone_type,
                min_value=requirements.basking_temp_min,
                max_value=requirements.basking_temp_max,
                warning_min=requirements.basking_temp_min - 2,
                warning_max=requirements.basking_temp_max + 2,
                hysteresis=1.0
            )
        elif zone_type == "cool_side":
            return cls(
                sensor_id=sensor_id,
                zone_type=zone_type,
                min_value=requirements.cool_side_temp_min,
                max_value=requirements.cool_side_temp_max,
                warning_min=requirements.cool_side_temp_min - 2,
                warning_max=requirements.cool_side_temp_max + 2,
                hysteresis=1.0
            )
        elif zone_type == "night":
            return cls(
                sensor_id=sensor_id,
                zone_type=zone_type,
                min_value=requirements.night_temp_min,
                max_value=requirements.night_temp_max,
                warning_min=requirements.night_temp_min - 2,
                warning_max=requirements.night_temp_max + 2,
                hysteresis=1.0
            )
        elif zone_type == "humidity":
            return cls(
                sensor_id=sensor_id,
                zone_type=zone_type,
                min_value=requirements.humidity_min,
                max_value=requirements.humidity_max,
                warning_min=requirements.humidity_min - 5,
                warning_max=requirements.humidity_max + 5,
                hysteresis=5.0  # Wider hysteresis for humidity
            )
        else:
            raise ValueError(f"Unknown zone type: {zone_type}")

    def create_heating_rules(
            self,
            habitat_id: str,
            outlet_id: str
    ) -> List['AutomationRule']:
        """
        Create both ON and OFF automation rules for heating equipment.
        Returns TWO rules: one to turn on when too cold, one to turn off when warm enough.
        """
        rules = []

        # Rule 1: Turn ON when temperature drops below minimum
        on_rule = AutomationRule(
            rule_id=f"{habitat_id}-{self.zone_type}-heat-on",
            name=f"Turn on {self.zone_type} heat when < {self.min_value}°C",
            habitat_id=habitat_id,
            sensor_id=self.sensor_id,
            outlet_id=outlet_id,
            trigger_value=self.min_value,
            trigger_operator='lt',
            action_on_trigger=OutletState.ON,
            action_on_clear=None,
            hysteresis=self.hysteresis,
            min_duration_seconds=300
        )
        rules.append(on_rule)

        # Rule 2: Turn OFF when temperature reaches maximum (with hysteresis)
        off_rule = AutomationRule(
            rule_id=f"{habitat_id}-{self.zone_type}-heat-off",
            name=f"Turn off {self.zone_type} heat when >= {self.max_value}°C",
            habitat_id=habitat_id,
            sensor_id=self.sensor_id,
            outlet_id=outlet_id,
            trigger_value=self.max_value,
            trigger_operator='gte',
            action_on_trigger=OutletState.OFF,
            action_on_clear=None,
            hysteresis=self.hysteresis,
            min_duration_seconds=300
        )
        rules.append(off_rule)

        return rules

    def create_humidity_rules(
            self,
            habitat_id: str,
            outlet_id: str
    ) -> List['AutomationRule']:
        """
        Create both ON and OFF automation rules for humidity equipment.
        Returns TWO rules: one to turn on when too dry, one to turn off when humid enough.
        """
        rules = []

        # Rule 1: Turn ON when humidity drops below minimum
        on_rule = AutomationRule(
            rule_id=f"{habitat_id}-humidity-on",
            name=f"Turn on humidifier when < {self.min_value}%",
            habitat_id=habitat_id,
            sensor_id=self.sensor_id,
            outlet_id=outlet_id,
            trigger_value=self.min_value,
            trigger_operator='lt',
            action_on_trigger=OutletState.ON,
            action_on_clear=None,
            hysteresis=self.hysteresis,
            min_duration_seconds=600  # Humidity changes slowly, wait longer
        )
        rules.append(on_rule)

        # Rule 2: Turn OFF when humidity reaches maximum (with hysteresis)
        off_rule = AutomationRule(
            rule_id=f"{habitat_id}-humidity-off",
            name=f"Turn off humidifier when >= {self.max_value}%",
            habitat_id=habitat_id,
            sensor_id=self.sensor_id,
            outlet_id=outlet_id,
            trigger_value=self.max_value,
            trigger_operator='gte',
            action_on_trigger=OutletState.OFF,
            action_on_clear=None,
            hysteresis=self.hysteresis,
            min_duration_seconds=600
        )
        rules.append(off_rule)

        return rules


@dataclass
class AutomationRule:
    """
    Rule for controlling equipment based on conditions.
    """
    rule_id: str
    name: str
    habitat_id: str
    sensor_id: str
    outlet_id: str

    trigger_value: float
    trigger_operator: str  # 'lt', 'gt', 'lte', 'gte', 'eq'
    action_on_trigger: OutletState
    action_on_clear: Optional[OutletState] = None

    # Prevent rapid cycling
    min_duration_seconds: int = 300  # 5 minutes
    hysteresis: float = 2.0

    enabled: bool = True
    last_triggered: Optional[datetime] = None

    def should_trigger(self, sensor_value: float) -> bool:
        """
        Business logic: Determine if rule should trigger based on sensor value.
        """
        if not self.enabled:
            return False

        # Check cooldown period
        if self.last_triggered:
            from datetime import datetime
            elapsed = (datetime.utcnow() - self.last_triggered).total_seconds()
            if elapsed < self.min_duration_seconds:
                return False

        # Evaluate condition based on operator
        if self.trigger_operator == 'gt':
            return sensor_value > self.trigger_value
        elif self.trigger_operator == 'lt':
            return sensor_value < self.trigger_value
        elif self.trigger_operator == 'gte':
            return sensor_value >= self.trigger_value
        elif self.trigger_operator == 'lte':
            return sensor_value <= self.trigger_value
        elif self.trigger_operator == 'eq':
            return abs(sensor_value - self.trigger_value) < 0.001
        else:
            raise ValueError(f"Unknown operator: {self.trigger_operator}")

    def should_clear(self, sensor_value: float) -> bool:
        """
        Business logic: Determine if rule condition has cleared.
        Uses hysteresis to prevent rapid switching.
        """
        if not self.enabled or self.action_on_clear is None:
            return False

        # Apply hysteresis based on original trigger
        threshold = self.trigger_value

        if self.trigger_operator == 'gt':
            # If triggered on value > threshold, clear when value < (threshold - hysteresis)
            return sensor_value < (threshold - self.hysteresis)
        elif self.trigger_operator == 'lt':
            # If triggered on value < threshold, clear when value > (threshold + hysteresis)
            return sensor_value > (threshold + self.hysteresis)
        elif self.trigger_operator == 'gte':
            return sensor_value < (threshold - self.hysteresis)
        elif self.trigger_operator == 'lte':
            return sensor_value > (threshold + self.hysteresis)

        return False

    @classmethod
    def from_threshold(
            cls,
            rule_id: str,
            habitat_id: str,
            threshold: Threshold,
            outlet_id: str,
            action_type: str = 'heat_on'  # 'heat_on', 'heat_off', 'humid_on', 'humid_off'
    ) -> 'AutomationRule':
        """
        Create automation rule from threshold.
        Business logic: How to respond to threshold violations.

        action_type determines which type of rule to create:
        - 'heat_on': Turn on heat when too cold (temp < min)
        - 'heat_off': Turn off heat when warm enough (temp >= max)
        - 'humid_on': Turn on humidifier when too dry (humidity < min)
        - 'humid_off': Turn off humidifier when humid enough (humidity >= max)
        """
        if action_type == 'heat_on':
            return cls(
                rule_id=rule_id,
                name=f"{threshold.zone_type} heating ON when < {threshold.min_value}°C",
                habitat_id=habitat_id,
                sensor_id=threshold.sensor_id,
                outlet_id=outlet_id,
                trigger_value=threshold.min_value,
                trigger_operator='lt',
                action_on_trigger=OutletState.ON,
                action_on_clear=None,
                hysteresis=threshold.hysteresis,
                min_duration_seconds=300
            )
        elif action_type == 'heat_off':
            return cls(
                rule_id=rule_id,
                name=f"{threshold.zone_type} heating OFF when >= {threshold.max_value}°C",
                habitat_id=habitat_id,
                sensor_id=threshold.sensor_id,
                outlet_id=outlet_id,
                trigger_value=threshold.max_value,
                trigger_operator='gte',
                action_on_trigger=OutletState.OFF,
                action_on_clear=None,
                hysteresis=threshold.hysteresis,
                min_duration_seconds=300
            )
        elif action_type == 'humid_on':
            return cls(
                rule_id=rule_id,
                name=f"Humidifier ON when < {threshold.min_value}%",
                habitat_id=habitat_id,
                sensor_id=threshold.sensor_id,
                outlet_id=outlet_id,
                trigger_value=threshold.min_value,
                trigger_operator='lt',
                action_on_trigger=OutletState.ON,
                action_on_clear=None,
                hysteresis=threshold.hysteresis,
                min_duration_seconds=600
            )
        elif action_type == 'humid_off':
            return cls(
                rule_id=rule_id,
                name=f"Humidifier OFF when >= {threshold.max_value}%",
                habitat_id=habitat_id,
                sensor_id=threshold.sensor_id,
                outlet_id=outlet_id,
                trigger_value=threshold.max_value,
                trigger_operator='gte',
                action_on_trigger=OutletState.OFF,
                action_on_clear=None,
                hysteresis=threshold.hysteresis,
                min_duration_seconds=600
            )
        else:
            raise ValueError(f"Unknown action_type: {action_type}")