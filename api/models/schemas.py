# api/models/schemas.py

"""
Pydantic schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from api.models.enums import (
    ReptileSpecies,
    SensorUnit,
    OutletState,
    ControlMode,
    AlertSeverity,
    SensorStatus,
    ThresholdStatus,
    DayNightMode,
    SystemHealth,
    TriggerOperator
)


# ============================================================
# Habitat Schemas
# ============================================================

class SensorConfig(BaseModel):
    basking_temp: str
    cool_temp: str
    humidity: str


class OutletConfig(BaseModel):
    heat_lamp: str
    ceramic_heater: Optional[str] = None
    uvb: Optional[str] = None
    humidifier: Optional[str] = None


class HabitatBase(BaseModel):
    name: str
    species: ReptileSpecies


class HabitatCreate(HabitatBase):
    habitat_id: str
    sensor_config: SensorConfig
    outlet_config: OutletConfig


class HabitatResponse(BaseModel):
    habitat_id: str
    name: str
    species: ReptileSpecies
    basking_temp_sensor_id: str
    cool_temp_sensor_id: str
    humidity_sensor_id: str
    heat_lamp_outlet_id: str
    ceramic_heater_outlet_id: Optional[str] = None
    uvb_outlet_id: Optional[str] = None
    humidifier_outlet_id: Optional[str] = None


class CurrentConditions(BaseModel):
    basking_temp: Optional[float] = None
    cool_temp: Optional[float] = None
    humidity: Optional[float] = None


class IdealConditions(BaseModel):
    basking_temp: str
    cool_temp: str
    humidity: str


class SensorStatusMap(BaseModel):
    basking_temp: ThresholdStatus
    cool_temp: ThresholdStatus
    humidity: ThresholdStatus


class HabitatStatusResponse(BaseModel):
    habitat_id: str
    name: str
    species: ReptileSpecies
    current_conditions: CurrentConditions
    ideal_conditions: IdealConditions
    sensor_status: SensorStatusMap
    outlets: dict
    overall_status: str


# ============================================================
# Species Schemas
# ============================================================

class SpeciesRequirementsResponse(BaseModel):
    species: ReptileSpecies
    basking_temp_min: float
    basking_temp_max: float
    cool_side_temp_min: float
    cool_side_temp_max: float
    night_temp_min: float
    night_temp_max: float
    humidity_min: float
    humidity_max: float
    uvb_required: bool
    substrate_type: Optional[str] = None
    notes: Optional[str] = None


# ============================================================
# Sensor Schemas
# ============================================================

class ThresholdInfo(BaseModel):
    min: float
    max: float
    zone_type: str


class SensorStatusResponse(BaseModel):
    sensor_id: str
    status: SensorStatus
    latest_value: Optional[float] = None
    latest_timestamp: Optional[datetime] = None
    is_valid: bool = True
    is_stale: bool = False
    threshold_status: ThresholdStatus = ThresholdStatus.UNKNOWN
    threshold: Optional[ThresholdInfo] = None


class SensorReadingResponse(BaseModel):
    value: float
    timestamp: datetime
    unit: SensorUnit
    is_valid: bool = True


class SensorReadingsListResponse(BaseModel):
    sensor_id: str
    readings: list[SensorReadingResponse]
    count: int


class SensorReadingCreate(BaseModel):
    value: float
    unit: str = "celsius"
    timestamp: Optional[datetime] = None


# ============================================================
# Outlet Schemas
# ============================================================

class RuleInfo(BaseModel):
    rule_id: str
    name: str
    sensor: str
    enabled: bool
    trigger: str


class OutletStatusResponse(BaseModel):
    outlet_id: str
    state: OutletState
    last_changed: Optional[datetime] = None
    mode: ControlMode = ControlMode.AUTOMATIC
    power_watts: Optional[float] = None
    rules: list[RuleInfo] = []


class OutletControlRequest(BaseModel):
    state: OutletState
    user: str


class OutletCommandResponse(BaseModel):
    command_id: str
    desired_state: OutletState
    reason: str
    triggered_by_sensor: Optional[str] = None
    triggered_by_user: Optional[str] = None
    timestamp: datetime
    executed: bool
    execution_result: Optional[str] = None


class OutletHistoryResponse(BaseModel):
    outlet_id: str
    commands: list[OutletCommandResponse]


# ============================================================
# Threshold Schemas
# ============================================================

class ThresholdResponse(BaseModel):
    sensor_id: str
    zone_type: str
    min_value: float
    max_value: float
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    hysteresis: float = 2.0


class ThresholdUpdate(BaseModel):
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    warning_min: Optional[float] = None
    warning_max: Optional[float] = None
    hysteresis: Optional[float] = None


# ============================================================
# Automation Rules Schemas
# ============================================================

class AutomationRuleBase(BaseModel):
    name: str
    habitat_id: str
    sensor_id: str
    outlet_id: str
    trigger_value: float
    trigger_operator: TriggerOperator
    action_on_trigger: OutletState
    action_on_clear: Optional[OutletState] = None
    min_duration_seconds: int = 300
    hysteresis: float = 2.0


class AutomationRuleCreate(AutomationRuleBase):
    rule_id: str


class AutomationRuleUpdate(BaseModel):
    name: Optional[str] = None
    trigger_value: Optional[float] = None
    trigger_operator: Optional[TriggerOperator] = None
    action_on_trigger: Optional[OutletState] = None
    action_on_clear: Optional[OutletState] = None
    min_duration_seconds: Optional[int] = None
    hysteresis: Optional[float] = None
    enabled: Optional[bool] = None


class AutomationRuleResponse(AutomationRuleBase):
    rule_id: str
    enabled: bool = True
    last_triggered: Optional[datetime] = None


# ============================================================
# Day/Night Schemas
# ============================================================

class DayNightStatusResponse(BaseModel):
    mode: DayNightMode
    is_day_mode: bool
    last_mode_change: Optional[datetime] = None
    sunrise: Optional[datetime] = None
    sunset: Optional[datetime] = None
    current_time: datetime
    registered_habitats: list[str] = []


class SunTimesResponse(BaseModel):
    date: str
    sunrise: datetime
    sunset: datetime
    is_daytime: bool


class ForceModeRequest(BaseModel):
    mode: DayNightMode


# ============================================================
# Alert Schemas
# ============================================================

class AlertResponse(BaseModel):
    alert_id: str
    sensor_id: str
    severity: AlertSeverity
    message: str
    value: float
    threshold_violated: Optional[str] = None
    created_at: datetime
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None


class AlertAcknowledgeRequest(BaseModel):
    user: str


# ============================================================
# System Status Schemas
# ============================================================

class SensorStats(BaseModel):
    total: int
    active: int
    stale: int


class OutletStats(BaseModel):
    total: int
    responsive: int
    errors: int


class HabitatStats(BaseModel):
    total: int
    in_range: int
    out_of_range: int


class SystemStatusResponse(BaseModel):
    status: SystemHealth
    database: str
    sensors: SensorStats
    outlets: OutletStats
    habitats: HabitatStats
    uptime_seconds: int


class DatabaseStatusResponse(BaseModel):
    connected: bool
    database: str
    collections: list[str]


# ============================================================
# Dashboard Schemas (iPad at-a-glance view)
# ============================================================

class HabitatSummary(BaseModel):
    """Compact habitat status for dashboard display."""
    habitat_id: str
    name: str
    species: ReptileSpecies
    status: str  # "ok", "warning", "critical"
    basking_temp_f: Optional[float] = None
    cool_temp_f: Optional[float] = None
    humidity: Optional[float] = None
    heat_lamp: str = "unknown"
    uvb: str = "unknown"
    last_reading: Optional[datetime] = None


class DashboardResponse(BaseModel):
    """All habitats at a glance for iPad monitoring."""
    timestamp: datetime
    system_status: SystemHealth
    mode: str  # "day" or "night"
    habitats: list[HabitatSummary]
    active_alerts: int
    total_habitats: int
    habitats_ok: int
    habitats_warning: int
    habitats_critical: int
