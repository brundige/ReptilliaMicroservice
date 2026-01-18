# Reptilia Microservice Architecture

## Overview

The Reptilia Microservice is a habitat automation system for reptile enclosures. It monitors environmental conditions (temperature, humidity) and automatically controls heating, lighting, and humidity equipment to maintain optimal conditions for reptile health.

## Architectural Pattern: Hexagonal Architecture (Ports & Adapters)

This project follows **Hexagonal Architecture** (also known as Ports and Adapters), originally proposed by Alistair Cockburn. This architecture isolates the core business logic from external concerns like databases, hardware, and APIs.

```
                    ┌─────────────────────────────────────────┐
                    │           DRIVING ADAPTERS              │
                    │  (Primary/Inbound - trigger actions)    │
                    │                                         │
                    │   ┌─────────┐  ┌─────────┐             │
                    │   │  CLI    │  │  API    │             │
                    │   │ main.py │  │ (future)│             │
                    │   └────┬────┘  └────┬────┘             │
                    └────────┼────────────┼──────────────────┘
                             │            │
                             ▼            ▼
              ┌──────────────────────────────────────────────┐
              │              INBOUND PORTS                    │
              │         (Service Interfaces)                  │
              └──────────────────────────────────────────────┘
                             │
                             ▼
    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │                    DOMAIN CORE                             │
    │                                                            │
    │   ┌──────────────────────────────────────────────────┐    │
    │   │                 SERVICES                          │    │
    │   │  ┌────────────────────┐ ┌────────────────────┐   │    │
    │   │  │ SensorMonitoring   │ │ OutletAutomation   │   │    │
    │   │  │     Service        │ │     Service        │   │    │
    │   │  └────────────────────┘ └────────────────────┘   │    │
    │   │  ┌────────────────────┐ ┌────────────────────┐   │    │
    │   │  │  HabitatManagement │ │   DayNightService  │   │    │
    │   │  │     Service        │ │                    │   │    │
    │   │  └────────────────────┘ └────────────────────┘   │    │
    │   │  ┌────────────────────┐                          │    │
    │   │  │ LightSchedule      │                          │    │
    │   │  │     Service        │                          │    │
    │   │  └────────────────────┘                          │    │
    │   └──────────────────────────────────────────────────┘    │
    │                                                            │
    │   ┌──────────────────────────────────────────────────┐    │
    │   │                   MODELS                          │    │
    │   │  SensorReading, Habitat, HabitatRequirements,    │    │
    │   │  AutomationRule, OutletState, LightSchedule,     │    │
    │   │  Threshold, Alert, HabitatDayNightConfig         │    │
    │   └──────────────────────────────────────────────────┘    │
    │                                                            │
    └────────────────────────────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────────────────────┐
              │              OUTBOUND PORTS                   │
              │     (Abstract Interfaces in ports.py)         │
              │                                               │
              │  SensorRepository    OutletController         │
              │  OutletRepository    SensorHardwareInterface  │
              │  HabitatRepository   NotificationService      │
              │  ThresholdRepository SunTimesProvider         │
              │  TimeProvider        Logger                   │
              └──────────────────────────────────────────────┘
                             │
                             ▼
                    ┌─────────────────────────────────────────┐
                    │          DRIVEN ADAPTERS                │
                    │  (Secondary/Outbound - called by core)  │
                    │                                         │
                    │  ┌──────────┐  ┌──────────────────┐    │
                    │  │ MongoDB  │  │  Kasa Smart      │    │
                    │  │ Repos    │  │  Outlets         │    │
                    │  └──────────┘  └──────────────────┘    │
                    │  ┌──────────┐  ┌──────────────────┐    │
                    │  │ BLE      │  │  Astral Sun      │    │
                    │  │ Sensors  │  │  Times           │    │
                    │  └──────────┘  └──────────────────┘    │
                    │  ┌──────────┐                          │
                    │  │ Mock     │  (for testing)           │
                    │  │ Adapters │                          │
                    │  └──────────┘                          │
                    └─────────────────────────────────────────┘
```

## Key Principles

### 1. Dependency Inversion
The domain core depends on **abstractions (ports)**, not concrete implementations. Adapters depend on the domain, not vice versa.

```python
# Port (abstract interface) - domain/ports.py
class SensorRepository(ABC):
    @abstractmethod
    def save_reading(self, reading: SensorReading) -> bool:
        pass

# Adapter (concrete implementation) - adapters/mongodb/repositories.py
class MongoDBSensorRepository(SensorRepository):
    def save_reading(self, reading: SensorReading) -> bool:
        # MongoDB-specific implementation
        self._collection.insert_one(reading.to_dict())
        return True
```

### 2. Domain Isolation
Business logic lives in the domain layer and has no knowledge of:
- Which database is used (MongoDB, PostgreSQL, in-memory)
- Which hardware controls outlets (Kasa, Tasmota, mock)
- How sensors communicate (BLE, WiFi, mock)

### 3. Testability
Mock adapters can replace real infrastructure for testing:

```python
# Test with mock adapters
sensor_repo = MockSensorRepository()
outlet_controller = MockOutletController()

# Production with real adapters
sensor_repo = MongoDBSensorRepository(db)
outlet_controller = KasaOutletController(ip="192.168.1.100")
```

---

## Project Structure

```
service/
├── domain/                    # CORE BUSINESS LOGIC
│   ├── models.py             # Domain entities and value objects
│   ├── ports.py              # Abstract interfaces (ports)
│   └── services.py           # Business logic services
│
├── adapters/                  # INFRASTRUCTURE IMPLEMENTATIONS
│   ├── mock/                 # Mock adapters for testing
│   │   ├── mock_sensor.py
│   │   ├── mock_outlet.py
│   │   └── mock_repositories.py
│   │
│   ├── mongodb/              # MongoDB persistence adapters
│   │   ├── connection.py
│   │   └── repositories.py
│   │
│   ├── sensors/              # Hardware sensor adapters
│   │   └── LYWSD03MMC.py    # Xiaomi BLE temperature sensor
│   │
│   ├── outlets/              # Smart outlet adapters
│   │   └── kasa.py          # TP-Link Kasa smart plugs
│   │
│   └── utils/                # Utility adapters
│       └── time_providers.py # Time and sun times providers
│
├── main.py                   # Application entry point (wiring)
└── requirements.txt
```

---

## Domain Layer

### Models (`domain/models.py`)

Domain models represent the core business concepts:

| Model | Purpose |
|-------|---------|
| `SensorReading` | A single temperature/humidity measurement |
| `Habitat` | Enclosure configuration (sensors, outlets, species) |
| `HabitatRequirements` | Species-specific environmental requirements |
| `AutomationRule` | Condition-based outlet control rule |
| `LightSchedule` | Time-based lighting schedule (supports sunrise/sunset) |
| `Threshold` | Min/max values for sensor alerts |
| `OutletState` | Current state of a smart outlet |
| `HabitatDayNightConfig` | Day/night transition configuration |

### Ports (`domain/ports.py`)

Ports define the interfaces the domain expects from external systems:

| Port | Purpose |
|------|---------|
| `SensorRepository` | Store/retrieve sensor readings |
| `SensorHardwareInterface` | Read from physical sensors |
| `OutletController` | Control smart outlets (on/off/state) |
| `OutletRepository` | Store outlet command history |
| `HabitatRepository` | Store/retrieve habitat configurations |
| `ThresholdRepository` | Store/retrieve alert thresholds |
| `NotificationService` | Send alerts (email, push, etc.) |
| `TimeProvider` | Get current time (mockable for testing) |
| `SunTimesProvider` | Get sunrise/sunset times |
| `Logger` | Log messages |

### Services (`domain/services.py`)

Services contain the business logic:

| Service | Responsibility |
|---------|----------------|
| `SensorMonitoringService` | Process readings, check thresholds, trigger automation |
| `OutletAutomationService` | Evaluate rules and control outlets |
| `HabitatManagementService` | Configure habitats with species requirements |
| `LightScheduleService` | Manage time-based lighting schedules |
| `DayNightService` | Handle sunrise/sunset transitions |
| `SensorPollingService` | Poll sensors on a schedule |

---

## Adapters Layer

### MongoDB Adapters (`adapters/mongodb/`)

Persistence adapters using MongoDB:

```python
class MongoDBSensorRepository(SensorRepository):
    """Stores sensor readings with 90-day TTL auto-expiry."""

class MongoDBHabitatRepository(HabitatRepository):
    """Stores habitat configs and species requirements."""
```

### Hardware Adapters (`adapters/sensors/`, `adapters/outlets/`)

```python
class LYWSD03MMCSensor(SensorHardwareInterface):
    """Reads from Xiaomi LYWSD03MMC BLE temperature sensors."""

class KasaOutletController(OutletController):
    """Controls TP-Link Kasa smart plugs/power strips."""
```

### Utility Adapters (`adapters/utils/`)

```python
class AstralSunTimesProvider(SunTimesProvider):
    """Calculates sunrise/sunset using astronomical algorithms."""

class SystemTimeProvider(TimeProvider):
    """Returns actual system time."""

class FixedTimeProvider(TimeProvider):
    """Returns configurable time for testing."""
```

---

## Day/Night Automation Feature

### How It Works

The `DayNightService` manages automatic transitions based on actual sunrise/sunset times:

```
SUNRISE                                              SUNSET
   │                                                    │
   ▼                                                    ▼
┌──────────────────── DAY MODE ─────────────────────────┐
│                                                       │
│  - UVB Light: ON                                      │
│  - Basking Heat Lamp: Controlled by temp rules        │
│  - Ceramic Heater: Controlled by temp rules           │
│                                                       │
└───────────────────────────────────────────────────────┘
   │                                                    │
   ▼                                                    ▼
┌─────────────────── NIGHT MODE ────────────────────────┐
│                                                       │
│  - UVB Light: OFF                                     │
│  - Basking Heat Lamp: OFF (no visible light at night) │
│  - Ceramic Heater: ON only if temp < night_temp_min   │
│                     OFF when temp >= night_temp_max   │
│                                                       │
└───────────────────────────────────────────────────────┘
```

### Night Heating Logic

At night, the ceramic heater (no visible light) maintains emergency heating:

```python
# Night heating rules (created automatically at sunset)
if cool_side_temp < night_temp_min:
    ceramic_heater.turn_on()

if cool_side_temp >= night_temp_max:
    ceramic_heater.turn_off()
```

This uses the `night_temp_min` and `night_temp_max` values from `HabitatRequirements`, which are species-specific (e.g., Leopard Geckos: 16-18°C at night).

### Sunrise/Sunset Calculation

Uses the `astral` library for accurate astronomical calculations:

```python
sun_times_provider = AstralSunTimesProvider(
    latitude=40.7128,      # Your location
    longitude=-74.0060,
    timezone_name="America/New_York"
)

sunrise = sun_times_provider.get_sunrise()  # e.g., 06:45
sunset = sun_times_provider.get_sunset()    # e.g., 19:30
```

---

## Configuration

### Environment Variables

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=reptilia

# Sensors (Xiaomi LYWSD03MMC BLE addresses)
SENSOR_WARM_SIDE_ADDRESS=BE67157C-68B0-1E7B-141E-89E563048735
SENSOR_WARM_SIDE_ID=basking-temp-sensor
SENSOR_COOL_SIDE_ADDRESS=763137C2-0D36-87EE-F64A-A21B387F16A1
SENSOR_COOL_SIDE_ID=cool-temp-sensor
SENSOR_CONNECTION_TIMEOUT=30.0
SENSOR_MAX_RETRIES=3

# Smart Outlets (Kasa)
KASA_IP=192.168.1.100
KASA_USERNAME=your_email@example.com
KASA_PASSWORD=your_password
KASA_OUTLET_MAPPING={"basking-heat-lamp": 0, "ambient-heater": 1, "humidifier": 2, "uvb-light": 3}

# Location (for sunrise/sunset)
HABITAT_LATITUDE=40.7128
HABITAT_LONGITUDE=-74.0060
HABITAT_TIMEZONE=America/New_York

# Polling
POLLING_INTERVAL_SECONDS=30
```

---

## Data Flow Example

### Sensor Reading Flow

```
1. BLE Sensor (hardware)
        │
        ▼
2. LYWSD03MMCSensor.read_temperature_and_humidity()
   [Adapter implements SensorHardwareInterface port]
        │
        ▼
3. SensorMonitoringService.process_reading()
   [Domain service - business logic]
        │
        ├──▶ Validate reading
        ├──▶ Save to MongoDBSensorRepository [via SensorRepository port]
        ├──▶ Check thresholds [via ThresholdRepository port]
        └──▶ Trigger OutletAutomationService
                    │
                    ▼
4. OutletAutomationService.process_sensor_reading()
   [Domain service evaluates AutomationRules]
        │
        ▼
5. KasaOutletController.turn_on() / turn_off()
   [Adapter implements OutletController port]
        │
        ▼
6. Physical outlet changes state
```

### Day/Night Transition Flow

```
1. Polling loop calls day_night.check_and_update()
        │
        ▼
2. AstralSunTimesProvider.is_daytime()
   [Adapter calculates based on lat/lon]
        │
        ▼
3. DayNightService detects mode change
        │
        ├──▶ SUNSET detected:
        │       - Turn OFF UVB [via OutletController port]
        │       - Turn OFF Heat Lamp [via OutletController port]
        │       - Disable daytime heating rules
        │       - Create & enable night heating rules
        │
        └──▶ SUNRISE detected:
                - Turn ON UVB [via OutletController port]
                - Enable daytime heating rules
                - Disable night heating rules
```

---

## Testing Strategy

The hexagonal architecture enables comprehensive testing:

### Unit Tests (Domain Logic)
Test services with mock adapters:

```python
def test_automation_triggers_on_low_temp():
    # Arrange
    outlet_controller = MockOutletController()
    automation = OutletAutomationService(outlet_controller, mock_repo)
    automation.register_rule(heating_rule)

    # Act
    commands = automation.process_sensor_reading(cold_reading)

    # Assert
    assert outlet_controller.get_state("heater").state == OutletStateEnum.ON
```

### Integration Tests
Test adapters with real infrastructure:

```python
def test_mongodb_saves_readings():
    repo = MongoDBSensorRepository(test_db)
    reading = SensorReading(sensor_id="test", value=25.0, ...)

    assert repo.save_reading(reading) == True
    assert repo.get_latest_reading("test").value == 25.0
```

### End-to-End Tests
Test full flows with mock hardware:

```python
def test_full_automation_cycle():
    app = create_test_app()  # Uses mock sensors and outlets

    # Simulate cold reading
    app['monitoring'].process_reading("sensor-1", value=15.0, ...)

    # Verify heater turned on
    assert app['outlet_controller'].get_state("heater").state == ON
```

---

## Adding New Adapters

### Example: Adding a Tasmota Outlet Adapter

1. **Create the adapter** (implements the port):

```python
# adapters/outlets/tasmota.py
from domain.ports import OutletController

class TasmotaOutletController(OutletController):
    def __init__(self, ip_address: str):
        self._ip = ip_address

    def turn_on(self, outlet_id: str) -> bool:
        # HTTP call to Tasmota device
        response = requests.get(f"http://{self._ip}/cm?cmnd=Power%20On")
        return response.status_code == 200

    def turn_off(self, outlet_id: str) -> bool:
        response = requests.get(f"http://{self._ip}/cm?cmnd=Power%20Off")
        return response.status_code == 200

    def get_state(self, outlet_id: str) -> OutletState:
        # Query current state
        ...
```

2. **Wire it up in main.py**:

```python
if os.getenv("OUTLET_TYPE") == "tasmota":
    outlet_controller = TasmotaOutletController(os.getenv("TASMOTA_IP"))
else:
    outlet_controller = KasaOutletController(...)
```

The domain layer remains unchanged - it only knows about the `OutletController` port.

---

## Benefits of This Architecture

| Benefit | Description |
|---------|-------------|
| **Testability** | Mock any external dependency for fast, reliable tests |
| **Flexibility** | Swap databases, hardware, or APIs without changing business logic |
| **Maintainability** | Clear separation makes code easier to understand and modify |
| **Domain Focus** | Business logic is explicit and not buried in infrastructure code |
| **Dependency Management** | All dependencies point inward toward the domain |

---

## References

- [Hexagonal Architecture by Alistair Cockburn](https://alistair.cockburn.us/hexagonal-architecture/)
- [Ports and Adapters Pattern](https://en.wikipedia.org/wiki/Hexagonal_architecture_(software))
- [Domain-Driven Design by Eric Evans](https://www.domainlanguage.com/ddd/)