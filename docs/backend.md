Reptilia Microservice - Backend API Endpoints

This document outlines potential REST API endpoints for the Reptile Habitat Automation System based on the MongoDB collections and domain models.

---

## Habitats

### `GET /api/habitats`
List all configured habitats.

**Response:**
```json
[
  {
    "habitat_id": "string",
    "name": "string",
    "species": "ball_python | corn_snake | bearded_dragon | leopard_gecko",
    "basking_temp_sensor_id": "string",
    "cool_temp_sensor_id": "string",
    "humidity_sensor_id": "string",
    "heat_lamp_outlet_id": "string",
    "ceramic_heater_outlet_id": "string | null",
    "uvb_outlet_id": "string | null",
    "humidifier_outlet_id": "string | null"
  }
]
```

### `GET /api/habitats/{habitat_id}`
Get a specific habitat configuration.

### `POST /api/habitats`
Create a new habitat configuration.

**Request Body:**
```json
{
  "habitat_id": "string",
  "name": "string",
  "species": "ball_python | corn_snake | bearded_dragon | leopard_gecko",
  "sensor_config": {
    "basking_temp": "sensor_id",
    "cool_temp": "sensor_id",
    "humidity": "sensor_id"
  },
  "outlet_config": {
    "heat_lamp": "outlet_id",
    "ceramic_heater": "outlet_id",
    "uvb": "outlet_id",
    "humidifier": "outlet_id"
  }
}
```

### `PUT /api/habitats/{habitat_id}`
Update an existing habitat configuration.

### `DELETE /api/habitats/{habitat_id}`
Delete a habitat configuration.

### `GET /api/habitats/{habitat_id}/status`
Get comprehensive habitat status including current conditions, ideal ranges, sensor status, and outlet states.

**Response:**
```json
{
  "habitat_id": "string",
  "name": "string",
  "species": "string",
  "current_conditions": {
    "basking_temp": 32.5,
    "cool_temp": 26.0,
    "humidity": 55.0
  },
  "ideal_conditions": {
    "basking_temp": "31-33°C",
    "cool_temp": "26-28°C",
    "humidity": "50-60%"
  },
  "sensor_status": {
    "basking_temp": "ok | too_low | too_high",
    "cool_temp": "ok | too_low | too_high",
    "humidity": "ok | too_low | too_high"
  },
  "outlets": { ... },
  "overall_status": "ok | out_of_range"
}
```

---

## Species Requirements

### `GET /api/species`
List all supported species and their requirements.

**Response:**
```json
[
  {
    "species": "ball_python",
    "basking_temp_min": 31.0,
    "basking_temp_max": 33.0,
    "cool_side_temp_min": 26.0,
    "cool_side_temp_max": 28.0,
    "night_temp_min": 24.0,
    "night_temp_max": 26.0,
    "humidity_min": 50.0,
    "humidity_max": 60.0,
    "uvb_required": false,
    "substrate_type": "cypress mulch",
    "notes": "Tropical species, needs higher humidity"
  }
]
```

### `GET /api/species/{species}`
Get requirements for a specific species.

---

## Sensors

### `GET /api/sensors/{sensor_id}/status`
Get current status of a sensor.

**Response:**
```json
{
  "sensor_id": "string",
  "status": "active | stale | no_data",
  "latest_value": 32.5,
  "latest_timestamp": "2025-01-16T12:00:00Z",
  "is_valid": true,
  "is_stale": false,
  "threshold_status": "ok | too_low | too_high | unknown",
  "threshold": {
    "min": 31.0,
    "max": 33.0,
    "zone_type": "basking"
  }
}
```

### `GET /api/sensors/{sensor_id}/readings`
Get historical readings for a sensor.

**Query Parameters:**
- `hours` (optional, default: 24) - Number of hours of history to retrieve
- `start_time` (optional) - Start of time range (ISO 8601)
- `end_time` (optional) - End of time range (ISO 8601)

**Response:**
```json
{
  "sensor_id": "string",
  "readings": [
    {
      "value": 32.5,
      "timestamp": "2025-01-16T12:00:00Z",
      "unit": "°C | °F | %",
      "is_valid": true
    }
  ],
  "count": 1440
}
```

### `POST /api/sensors/{sensor_id}/readings`
Submit a new sensor reading (for external sensor integrations).

**Request Body:**
```json
{
  "value": 32.5,
  "unit": "celsius | fahrenheit | percent",
  "timestamp": "2025-01-16T12:00:00Z"
}
```

### `GET /api/habitats/{habitat_id}/readings`
Get all sensor readings for a habitat within a time range.

---

## Outlets

### `GET /api/outlets/{outlet_id}/status`
Get current status of an outlet.

**Response:**
```json
{
  "outlet_id": "string",
  "state": "on | off | unknown | error",
  "last_changed": "2025-01-16T12:00:00Z",
  "mode": "manual | automatic | override",
  "power_watts": 75.0,
  "rules": [
    {
      "rule_id": "string",
      "name": "Basking heating ON when < 31°C",
      "sensor": "sensor_id",
      "enabled": true,
      "trigger": "lt 31.0"
    }
  ]
}
```

### `POST /api/outlets/{outlet_id}/control`
Manually control an outlet (override automation).

**Request Body:**
```json
{
  "state": "on | off",
  "user": "string"
}
```

### `GET /api/outlets/{outlet_id}/history`
Get command history for an outlet.

**Query Parameters:**
- `start_time` (optional) - Start of time range
- `end_time` (optional) - End of time range

**Response:**
```json
{
  "outlet_id": "string",
  "commands": [
    {
      "command_id": "string",
      "desired_state": "on | off",
      "reason": "Manual control | Automation: rule_name",
      "triggered_by_sensor": "sensor_id | null",
      "triggered_by_user": "username | null",
      "timestamp": "2025-01-16T12:00:00Z",
      "executed": true,
      "execution_result": "success | failed"
    }
  ]
}
```

---

## Thresholds

### `GET /api/thresholds/{sensor_id}`
Get threshold configuration for a sensor.

**Response:**
```json
{
  "sensor_id": "string",
  "zone_type": "basking | cool_side | night | humidity",
  "min_value": 31.0,
  "max_value": 33.0,
  "warning_min": 29.0,
  "warning_max": 35.0,
  "hysteresis": 2.0
}
```

### `PUT /api/thresholds/{sensor_id}`
Update threshold configuration (override species defaults).

**Request Body:**
```json
{
  "min_value": 30.0,
  "max_value": 34.0,
  "warning_min": 28.0,
  "warning_max": 36.0,
  "hysteresis": 1.5
}
```

### `GET /api/habitats/{habitat_id}/thresholds`
Get all thresholds for a habitat.

---

## Automation Rules

### `GET /api/rules`
List all registered automation rules.

**Response:**
```json
[
  {
    "rule_id": "string",
    "name": "string",
    "habitat_id": "string",
    "sensor_id": "string",
    "outlet_id": "string",
    "trigger_value": 31.0,
    "trigger_operator": "lt | gt | lte | gte | eq",
    "action_on_trigger": "on | off",
    "action_on_clear": "on | off | null",
    "min_duration_seconds": 300,
    "hysteresis": 2.0,
    "enabled": true,
    "last_triggered": "2025-01-16T12:00:00Z"
  }
]
```

### `GET /api/rules/{rule_id}`
Get a specific automation rule.

### `POST /api/rules`
Create a custom automation rule.

### `PUT /api/rules/{rule_id}`
Update an automation rule.

### `DELETE /api/rules/{rule_id}`
Delete an automation rule.

### `POST /api/rules/{rule_id}/enable`
Enable a disabled rule.

### `POST /api/rules/{rule_id}/disable`
Temporarily disable a rule.

---

## Day/Night Control

### `GET /api/daynight/status`
Get current day/night status.

**Response:**
```json
{
  "mode": "day | night",
  "is_day_mode": true,
  "last_mode_change": "2025-01-16T07:15:00Z",
  "sunrise": "2025-01-16T07:15:00Z",
  "sunset": "2025-01-16T17:30:00Z",
  "current_time": "2025-01-16T12:00:00Z",
  "registered_habitats": ["habitat-1", "habitat-2"]
}
```

### `GET /api/daynight/sun-times`
Get sunrise and sunset times.

**Query Parameters:**
- `date` (optional) - Date to get times for (defaults to today)

**Response:**
```json
{
  "date": "2025-01-16",
  "sunrise": "2025-01-16T07:15:00Z",
  "sunset": "2025-01-16T17:30:00Z",
  "is_daytime": true
}
```

### `POST /api/daynight/force-mode`
Force day or night mode (for testing/override).

**Request Body:**
```json
{
  "mode": "day | night"
}
```

---

## Alerts

### `GET /api/alerts`
Get recent alerts.

**Query Parameters:**
- `sensor_id` (optional) - Filter by sensor
- `severity` (optional) - Filter by severity: `info | warning | critical`
- `acknowledged` (optional) - Filter by acknowledged status
- `limit` (optional, default: 50) - Max alerts to return

**Response:**
```json
[
  {
    "alert_id": "string",
    "sensor_id": "string",
    "severity": "info | warning | critical",
    "message": "sensor-1 critically low: 28.5°C < 31.0°C",
    "value": 28.5,
    "threshold_violated": "min: 31.0",
    "created_at": "2025-01-16T12:00:00Z",
    "acknowledged": false,
    "acknowledged_at": null,
    "acknowledged_by": null
  }
]
```

### `POST /api/alerts/{alert_id}/acknowledge`
Acknowledge an alert.

**Request Body:**
```json
{
  "user": "string"
}
```

---

## System Status

### `GET /api/status`
Get overall system health status.

**Response:**
```json
{
  "status": "healthy | degraded | unhealthy",
  "database": "connected | disconnected",
  "sensors": {
    "total": 6,
    "active": 5,
    "stale": 1
  },
  "outlets": {
    "total": 4,
    "responsive": 4,
    "errors": 0
  },
  "habitats": {
    "total": 2,
    "in_range": 1,
    "out_of_range": 1
  },
  "uptime_seconds": 86400
}
```

### `GET /api/status/database`
Check database connectivity.

---

## WebSocket Endpoints (Real-time Updates)

### `WS /ws/readings`
Subscribe to real-time sensor readings.

**Message format (server -> client):**
```json
{
  "type": "sensor_reading",
  "data": {
    "sensor_id": "string",
    "value": 32.5,
    "unit": "°C",
    "timestamp": "2025-01-16T12:00:00Z"
  }
}
```

### `WS /ws/alerts`
Subscribe to real-time alerts.

### `WS /ws/outlets`
Subscribe to outlet state changes.

---

## MongoDB Collections Reference

| Collection | Description |
|------------|-------------|
| `sensor_readings` | Time-series sensor data (90-day TTL) |
| `outlet_commands` | Audit trail of outlet commands |
| `outlet_states` | Current state of each outlet |
| `habitats` | Habitat configurations |
| `habitat_requirements` | Species-specific requirements (pre-seeded) |
| `thresholds` | Threshold configurations per sensor |