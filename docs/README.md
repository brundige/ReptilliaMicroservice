# Reptilia Microservice

A habitat automation system for reptile enclosures. Monitors temperature and humidity, automatically controls heating/cooling equipment, and manages day/night lighting cycles based on actual sunrise/sunset times.

## Features

- **Sensor Monitoring** - BLE temperature/humidity sensors (Xiaomi LYWSD03MMC)
- **Smart Outlet Control** - TP-Link Kasa smart plugs and power strips
- **Automated Climate Control** - Rule-based heating, cooling, and humidity management
- **Day/Night Cycles** - Automatic sunrise/sunset transitions using astronomical calculations
- **Species Profiles** - Pre-configured requirements for common reptile species
- **Persistent Storage** - MongoDB with automatic 90-day data retention

## Architecture

This project uses **Hexagonal Architecture** (Ports and Adapters) for clean separation between business logic and infrastructure. See [docs/ARCHITECTURE.md](ARCHITECTURE.md) for details.

```
┌─────────────────────────────────────────────────────┐
│                   DOMAIN CORE                       │
│  Services: Monitoring, Automation, Day/Night        │
│  Models: Habitat, Sensor, Outlet, Schedule          │
│  Ports: Repository, Controller, Provider interfaces │
└─────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────┐
│                    ADAPTERS                         │
│  MongoDB | Kasa Outlets | BLE Sensors | Astral      │
└─────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd service
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and edit with your settings:

```bash
cp .env.example .env
```

Key settings:

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=reptilia

# Location (for sunrise/sunset calculation)
HABITAT_LATITUDE=40.7128
HABITAT_LONGITUDE=-74.0060
HABITAT_TIMEZONE=America/New_York

# Kasa Smart Outlets
KASA_IP=192.168.1.100
KASA_OUTLET_MAPPING={"basking-heat-lamp": 0, "ambient-heater": 1, "humidifier": 2, "uvb-light": 3}

# BLE Sensors (get addresses from your Xiaomi sensors)
SENSOR_WARM_SIDE_ADDRESS=XX:XX:XX:XX:XX:XX
SENSOR_COOL_SIDE_ADDRESS=XX:XX:XX:XX:XX:XX
```

### 3. Start MongoDB

```bash
# Using Docker
docker run -d -p 27017:27017 --name reptilia-mongo mongo:7

# Or install locally
brew install mongodb-community  # macOS
```

### 4. Run the Application

```bash
cd service
python main.py
```

## Day/Night Automation

The system automatically manages lighting and heating based on sunrise/sunset:

| Mode | UVB Light | Heat Lamp | Ceramic Heater |
|------|-----------|-----------|----------------|
| **Day** (sunrise to sunset) | ON | Temp-controlled | Temp-controlled |
| **Night** (sunset to sunrise) | OFF | OFF | Only if temp < night_min |

Night heating maintains the cool side between `night_temp_min` and `night_temp_max` (species-specific values from the habitat configuration).

### Example Output

```
============================================================
🦎 REPTILE HABITAT AUTOMATION SYSTEM
============================================================

📦 Creating adapters...
  ✓ Warm side sensor created: basking-temp-sensor
  ✓ Cool side sensor created: cool-temp-sensor
  ✓ Kasa outlet controller created (device: 192.168.1.100)
  ✓ Sun times provider created (lat: 40.7128, lon: -74.006)
  ✓ Day/Night service created

🦎 Setting up test habitat...
✅ Habitat configured successfully!
   Name: Garys Leopard Gecko Enclosure
   Species: leopard_gecko
   Basking temp: 32°C - 35°C
   Cool temp: 24°C - 27°C

☀️  Day/Night Schedule:
   Sunrise: 06:45 (UVB ON)
   Sunset:  19:32 (UVB OFF, Heat lamp OFF)
   Night temp range: 16°C - 18°C

============================================================
🔄 STARTING SENSOR POLLING LOOP
============================================================

[14:23:15] Iteration #1
  🌡️  Warm side: 89.6°F, 45% humidity
  🌡️  Cool side: 77.0°F, 52% humidity
  🔌 UVB Light: 💡 ON
  🔌 Heat Lamp: 🔥 ON
  🔌 Humidifier: ⚫ OFF
  ⏰ Mode: ☀️ DAY
```

## Hardware Requirements

### Sensors
- **Xiaomi LYWSD03MMC** - BLE temperature/humidity sensors
- Flash with [ATC firmware](https://github.com/atc1441/ATC_MiThermometer) for better BLE support

### Smart Outlets
- **TP-Link Kasa** smart plugs (HS103, HS105) or power strips (HS300)
- Configure via Kasa app first, then use IP address

## Project Structure

```
service/
├── domain/           # Business logic (framework-independent)
│   ├── models.py    # Domain entities
│   ├── ports.py     # Abstract interfaces
│   └── services.py  # Business services
│
├── adapters/         # Infrastructure implementations
│   ├── mongodb/     # Database adapters
│   ├── sensors/     # BLE sensor adapters
│   ├── outlets/     # Smart outlet adapters
│   └── utils/       # Time/utility adapters
│
├── main.py          # Application entry point
└── requirements.txt
```

## Supported Species

The system includes pre-configured habitat requirements for:

| Species | Basking Temp | Cool Side | Night Temp | Humidity |
|---------|--------------|-----------|------------|----------|
| Leopard Gecko | 32-35°C | 24-27°C | 16-18°C | 30-40% |
| Ball Python | 32-35°C | 26-28°C | 24-26°C | 50-60% |
| Bearded Dragon | 38-43°C | 26-30°C | 18-24°C | 30-40% |
| Corn Snake | 28-32°C | 21-24°C | 18-21°C | 40-60% |

## API Reference

### Services

| Service | Purpose |
|---------|---------|
| `SensorMonitoringService` | Process sensor readings, check thresholds |
| `OutletAutomationService` | Evaluate rules, control outlets |
| `HabitatManagementService` | Configure habitats with species profiles |
| `DayNightService` | Manage sunrise/sunset transitions |
| `LightScheduleService` | Time-based lighting schedules |

### Ports (Interfaces)

| Port | Purpose |
|------|---------|
| `SensorRepository` | Persist sensor readings |
| `OutletController` | Control smart outlets |
| `SunTimesProvider` | Get sunrise/sunset times |
| `TimeProvider` | Get current time (mockable) |

## Development

### Running with Mock Hardware

Without configuring real hardware, the system uses mock adapters:

```bash
# No KASA_IP = mock outlet controller
# No sensor addresses = will fail sensor reads but continue running
python main.py
```

### Testing

```bash
pytest tests/
```

### Adding New Outlet Adapters

See [docs/ARCHITECTURE.md](ARCHITECTURE.md#adding-new-adapters) for examples of adding new hardware support.

## License

MIT

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make changes following the hexagonal architecture pattern
4. Add tests for new functionality
5. Submit a pull request