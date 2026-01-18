# api/models/__init__.py

from api.models.enums import (
    ReptileSpecies,
    SensorUnit,
    OutletState,
    ControlMode,
    AlertSeverity,
    SensorStatus,
    ThresholdStatus,
    DayNightMode,
    SystemHealth
)

from api.models.schemas import (
    # Habitats
    HabitatBase,
    HabitatCreate,
    HabitatResponse,
    HabitatStatusResponse,
    SensorConfig,
    OutletConfig,
    # Species
    SpeciesRequirementsResponse,
    # Sensors
    SensorStatusResponse,
    SensorReadingResponse,
    SensorReadingsListResponse,
    SensorReadingCreate,
    # Outlets
    OutletStatusResponse,
    OutletControlRequest,
    OutletCommandResponse,
    OutletHistoryResponse,
    # Thresholds
    ThresholdResponse,
    ThresholdUpdate,
    # Rules
    AutomationRuleResponse,
    AutomationRuleCreate,
    AutomationRuleUpdate,
    # Day/Night
    DayNightStatusResponse,
    SunTimesResponse,
    ForceModeRequest,
    # Alerts
    AlertResponse,
    AlertAcknowledgeRequest,
    # System
    SystemStatusResponse
)
