# api/routers/habitats.py

"""
Habitat endpoints for the Reptilia API.
"""

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    HabitatCreate,
    HabitatResponse,
    HabitatStatusResponse,
    CurrentConditions,
    IdealConditions,
    SensorStatusMap,
    SensorReadingsListResponse,
    SensorReadingResponse,
    SensorHardwareConfig,
    OutletHardwareConfig,
    PowerStripConfig,
    SensorLocation
)
from api.models.enums import ReptileSpecies, ThresholdStatus, SensorUnit

router = APIRouter(prefix="/habitats", tags=["Habitats"])


@router.get("", response_model=list[HabitatResponse])
def list_habitats(db: Database = Depends(get_db)):
    """List all configured habitats."""
    habitats = list(db.habitats.find({}))
    return [_doc_to_response(h) for h in habitats]


@router.get("/{habitat_id}", response_model=HabitatResponse)
def get_habitat(habitat_id: str, db: Database = Depends(get_db)):
    """Get a specific habitat configuration."""
    habitat = db.habitats.find_one({"habitat_id": habitat_id})
    if not habitat:
        raise HTTPException(status_code=404, detail="Habitat not found")
    return _doc_to_response(habitat)


@router.post("", response_model=HabitatResponse, status_code=201)
def create_habitat(habitat: HabitatCreate, db: Database = Depends(get_db)):
    """Create a new habitat configuration with optional embedded hardware config."""
    # Check if habitat already exists
    existing = db.habitats.find_one({"habitat_id": habitat.habitat_id})
    if existing:
        raise HTTPException(status_code=409, detail="Habitat already exists")

    # Build embedded sensors document
    sensors_docs = []
    if habitat.sensors:
        for sensor in habitat.sensors:
            sensors_docs.append({
                "sensor_id": sensor.sensor_id,
                "ble_address": sensor.ble_address,
                "location": sensor.location.value,
                "device_type": sensor.device_type
            })

    # Build embedded power_strip document
    power_strip_doc = None
    if habitat.power_strip:
        outlets_docs = []
        for outlet in habitat.power_strip.outlets:
            outlets_docs.append({
                "outlet_id": outlet.outlet_id,
                "plug_number": outlet.plug_number
            })
        power_strip_doc = {
            "strip_id": habitat.power_strip.strip_id,
            "ip": habitat.power_strip.ip,
            "username": habitat.power_strip.username,
            "password": habitat.power_strip.password,
            "outlets": outlets_docs
        }

    doc = {
        "habitat_id": habitat.habitat_id,
        "name": habitat.name,
        "species": habitat.species.value,
        "sensors": sensors_docs,
        "power_strip": power_strip_doc,
        "basking_temp_sensor_id": habitat.sensor_config.basking_temp,
        "cool_temp_sensor_id": habitat.sensor_config.cool_temp,
        "humidity_sensor_id": habitat.sensor_config.humidity,
        "heat_lamp_outlet_id": habitat.outlet_config.heat_lamp,
        "ceramic_heater_outlet_id": habitat.outlet_config.ceramic_heater,
        "uvb_outlet_id": habitat.outlet_config.uvb,
        "humidifier_outlet_id": habitat.outlet_config.humidifier
    }

    db.habitats.insert_one(doc)
    return _doc_to_response(doc)


@router.put("/{habitat_id}", response_model=HabitatResponse)
def update_habitat(
    habitat_id: str,
    habitat: HabitatCreate,
    db: Database = Depends(get_db)
):
    """Update an existing habitat configuration with optional hardware config."""
    existing = db.habitats.find_one({"habitat_id": habitat_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Habitat not found")

    # Build embedded sensors document
    sensors_docs = []
    if habitat.sensors:
        for sensor in habitat.sensors:
            sensors_docs.append({
                "sensor_id": sensor.sensor_id,
                "ble_address": sensor.ble_address,
                "location": sensor.location.value,
                "device_type": sensor.device_type
            })

    # Build embedded power_strip document
    power_strip_doc = None
    if habitat.power_strip:
        outlets_docs = []
        for outlet in habitat.power_strip.outlets:
            outlets_docs.append({
                "outlet_id": outlet.outlet_id,
                "plug_number": outlet.plug_number
            })
        power_strip_doc = {
            "strip_id": habitat.power_strip.strip_id,
            "ip": habitat.power_strip.ip,
            "username": habitat.power_strip.username,
            "password": habitat.power_strip.password,
            "outlets": outlets_docs
        }

    doc = {
        "habitat_id": habitat_id,
        "name": habitat.name,
        "species": habitat.species.value,
        "sensors": sensors_docs,
        "power_strip": power_strip_doc,
        "basking_temp_sensor_id": habitat.sensor_config.basking_temp,
        "cool_temp_sensor_id": habitat.sensor_config.cool_temp,
        "humidity_sensor_id": habitat.sensor_config.humidity,
        "heat_lamp_outlet_id": habitat.outlet_config.heat_lamp,
        "ceramic_heater_outlet_id": habitat.outlet_config.ceramic_heater,
        "uvb_outlet_id": habitat.outlet_config.uvb,
        "humidifier_outlet_id": habitat.outlet_config.humidifier
    }

    db.habitats.update_one({"habitat_id": habitat_id}, {"$set": doc})
    return _doc_to_response(doc)


@router.delete("/{habitat_id}", status_code=204)
def delete_habitat(habitat_id: str, db: Database = Depends(get_db)):
    """Delete a habitat configuration."""
    result = db.habitats.delete_one({"habitat_id": habitat_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habitat not found")


@router.get("/{habitat_id}/status", response_model=HabitatStatusResponse)
def get_habitat_status(habitat_id: str, db: Database = Depends(get_db)):
    """Get comprehensive habitat status."""
    habitat = db.habitats.find_one({"habitat_id": habitat_id})
    if not habitat:
        raise HTTPException(status_code=404, detail="Habitat not found")

    # Get species requirements
    requirements = db.habitat_requirements.find_one({"species": habitat["species"]})

    # Get latest sensor readings
    basking_reading = _get_latest_reading(db, habitat["basking_temp_sensor_id"])
    cool_reading = _get_latest_reading(db, habitat["cool_temp_sensor_id"])
    humidity_reading = _get_latest_reading(db, habitat["humidity_sensor_id"])

    # Get outlet states
    outlets = {}
    for outlet_key in ["heat_lamp_outlet_id", "ceramic_heater_outlet_id", "uvb_outlet_id", "humidifier_outlet_id"]:
        outlet_id = habitat.get(outlet_key)
        if outlet_id:
            state = db.outlet_states.find_one({"outlet_id": outlet_id})
            outlets[outlet_key.replace("_outlet_id", "")] = state["state"] if state else "unknown"

    # Determine status for each sensor
    basking_status = _check_threshold(
        basking_reading,
        requirements["basking_temp_min"] if requirements else None,
        requirements["basking_temp_max"] if requirements else None
    )
    cool_status = _check_threshold(
        cool_reading,
        requirements["cool_side_temp_min"] if requirements else None,
        requirements["cool_side_temp_max"] if requirements else None
    )
    humidity_status = _check_threshold(
        humidity_reading,
        requirements["humidity_min"] if requirements else None,
        requirements["humidity_max"] if requirements else None
    )

    # Overall status
    statuses = [basking_status, cool_status, humidity_status]
    overall = "ok" if all(s == ThresholdStatus.OK for s in statuses) else "out_of_range"

    return HabitatStatusResponse(
        habitat_id=habitat_id,
        name=habitat["name"],
        species=ReptileSpecies(habitat["species"]),
        current_conditions=CurrentConditions(
            basking_temp=basking_reading,
            cool_temp=cool_reading,
            humidity=humidity_reading
        ),
        ideal_conditions=IdealConditions(
            basking_temp=f"{requirements['basking_temp_min']}-{requirements['basking_temp_max']}°C" if requirements else "N/A",
            cool_temp=f"{requirements['cool_side_temp_min']}-{requirements['cool_side_temp_max']}°C" if requirements else "N/A",
            humidity=f"{requirements['humidity_min']}-{requirements['humidity_max']}%" if requirements else "N/A"
        ),
        sensor_status=SensorStatusMap(
            basking_temp=basking_status,
            cool_temp=cool_status,
            humidity=humidity_status
        ),
        outlets=outlets,
        overall_status=overall
    )


@router.get("/{habitat_id}/readings", response_model=SensorReadingsListResponse)
def get_habitat_readings(
    habitat_id: str,
    hours: int = 24,
    db: Database = Depends(get_db)
):
    """Get all sensor readings for a habitat within a time range."""
    habitat = db.habitats.find_one({"habitat_id": habitat_id})
    if not habitat:
        raise HTTPException(status_code=404, detail="Habitat not found")

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    sensor_ids = [
        habitat["basking_temp_sensor_id"],
        habitat["cool_temp_sensor_id"],
        habitat["humidity_sensor_id"]
    ]

    readings = list(db.sensor_readings.find({
        "sensor_id": {"$in": sensor_ids},
        "timestamp": {"$gte": start_time, "$lte": end_time}
    }).sort("timestamp", 1))

    return SensorReadingsListResponse(
        sensor_id=habitat_id,
        readings=[
            SensorReadingResponse(
                value=r["value"],
                timestamp=r["timestamp"],
                unit=SensorUnit(r["unit"]),
                is_valid=r.get("is_valid", True)
            )
            for r in readings
        ],
        count=len(readings)
    )


def _doc_to_response(doc: dict) -> HabitatResponse:
    """Convert MongoDB document to response model."""
    # Parse embedded sensors
    sensors = None
    if doc.get("sensors"):
        sensors = [
            SensorHardwareConfig(
                sensor_id=s["sensor_id"],
                ble_address=s["ble_address"],
                location=SensorLocation(s["location"]),
                device_type=s.get("device_type", "LYWSD03MMC")
            )
            for s in doc["sensors"]
        ]

    # Parse embedded power_strip
    power_strip = None
    if doc.get("power_strip"):
        ps = doc["power_strip"]
        outlets = [
            OutletHardwareConfig(
                outlet_id=o["outlet_id"],
                plug_number=o["plug_number"]
            )
            for o in ps.get("outlets", [])
        ]
        power_strip = PowerStripConfig(
            strip_id=ps["strip_id"],
            ip=ps["ip"],
            username=ps["username"],
            password=ps["password"],
            outlets=outlets
        )

    return HabitatResponse(
        habitat_id=doc["habitat_id"],
        name=doc["name"],
        species=ReptileSpecies(doc["species"]),
        basking_temp_sensor_id=doc.get("basking_temp_sensor_id", ""),
        cool_temp_sensor_id=doc.get("cool_temp_sensor_id", ""),
        humidity_sensor_id=doc.get("humidity_sensor_id", ""),
        heat_lamp_outlet_id=doc.get("heat_lamp_outlet_id", ""),
        ceramic_heater_outlet_id=doc.get("ceramic_heater_outlet_id"),
        uvb_outlet_id=doc.get("uvb_outlet_id"),
        humidifier_outlet_id=doc.get("humidifier_outlet_id"),
        sensors=sensors,
        power_strip=power_strip
    )


def _get_latest_reading(db: Database, sensor_id: str) -> float | None:
    """Get latest reading value for a sensor."""
    reading = db.sensor_readings.find_one(
        {"sensor_id": sensor_id},
        sort=[("timestamp", -1)]
    )
    return reading["value"] if reading else None


def _check_threshold(value: float | None, min_val: float | None, max_val: float | None) -> ThresholdStatus:
    """Check if value is within threshold."""
    if value is None or min_val is None or max_val is None:
        return ThresholdStatus.UNKNOWN
    if value < min_val:
        return ThresholdStatus.TOO_LOW
    if value > max_val:
        return ThresholdStatus.TOO_HIGH
    return ThresholdStatus.OK
