# adapters/mongodb/repositories.py

"""
MongoDB repository implementations for the Reptile Habitat Automation System.

These adapters implement the repository ports defined in domain/ports.py,
storing data in MongoDB collections.
"""

from typing import List, Optional
from datetime import datetime

from pymongo.database import Database
from pymongo import ASCENDING, DESCENDING

from domain.ports import (
    SensorRepository,
    OutletRepository,
    HabitatRepository,
    ThresholdRepository
)
from domain.models import (
    SensorReading,
    SensorUnit,
    OutletCommand,
    OutletState,
    OutletStateEnum,
    ControlMode,
    Habitat,
    HabitatRequirements,
    ReptileSpecies,
    Threshold,
    SensorConfig,
    SensorLocation,
    OutletConfig,
    PowerStripConfig
)


class MongoDBSensorRepository(SensorRepository):
    """
    MongoDB adapter for storing sensor readings.

    Collection: sensor_readings
    Indexes:
        - (sensor_id, timestamp) for efficient queries
        - TTL index on timestamp for automatic cleanup
    """

    COLLECTION_NAME = "sensor_readings"
    TTL_SECONDS = 90 * 24 * 60 * 60  # 90 days

    def __init__(self, database: Database):
        self._db = database
        self._collection = database[self.COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes if they don't exist."""
        # Compound index for efficient sensor + time queries
        self._collection.create_index(
            [("sensor_id", ASCENDING), ("timestamp", DESCENDING)],
            name="sensor_timestamp_idx"
        )
        # NEW: Compound index for habitat + time queries
        self._collection.create_index(
            [("habitat_id", ASCENDING), ("timestamp", DESCENDING)],
            name="habitat_timestamp_idx"
        )
        # TTL index for automatic cleanup after 90 days
        self._collection.create_index(
            "timestamp",
            expireAfterSeconds=self.TTL_SECONDS,
            name="ttl_idx"
        )

    def save_reading(self, reading: SensorReading) -> bool:
        """Save a sensor reading to MongoDB."""
        doc = {
            "sensor_id": reading.sensor_id,
            "value": reading.value,
            "timestamp": reading.timestamp,
            "unit": reading.unit.value,
            "is_valid": reading.is_valid
        }
        # Include habitat_id if present
        if reading.habitat_id:
            doc["habitat_id"] = reading.habitat_id
        result = self._collection.insert_one(doc)
        return result.acknowledged

    def get_readings(
        self,
        sensor_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[SensorReading]:
        """Get readings for a sensor within a time range."""
        cursor = self._collection.find({
            "sensor_id": sensor_id,
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }).sort("timestamp", ASCENDING)

        return [self._doc_to_reading(doc) for doc in cursor]

    def get_latest_reading(self, sensor_id: str) -> Optional[SensorReading]:
        """Get the most recent reading for a sensor."""
        doc = self._collection.find_one(
            {"sensor_id": sensor_id},
            sort=[("timestamp", DESCENDING)]
        )
        return self._doc_to_reading(doc) if doc else None

    def get_readings_by_habitat(
        self,
        habitat_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[SensorReading]:
        """Get all readings for a habitat within a time range."""
        # Now uses habitat_id field directly stored on readings
        cursor = self._collection.find({
            "habitat_id": habitat_id,
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }).sort("timestamp", ASCENDING)

        return [self._doc_to_reading(doc) for doc in cursor]

    def count(self) -> int:
        """Get total number of readings stored."""
        return self._collection.count_documents({})

    @staticmethod
    def _doc_to_reading(doc: dict) -> SensorReading:
        """Convert MongoDB document to SensorReading."""
        return SensorReading(
            sensor_id=doc["sensor_id"],
            value=doc["value"],
            timestamp=doc["timestamp"],
            unit=SensorUnit(doc["unit"]),
            is_valid=doc.get("is_valid", True),
            habitat_id=doc.get("habitat_id")
        )


class MongoDBOutletRepository(OutletRepository):
    """
    MongoDB adapter for storing outlet commands and states.

    Collections:
        - outlet_commands: Audit trail of all commands
        - outlet_states: Current state of each outlet
    """

    COMMANDS_COLLECTION = "outlet_commands"
    STATES_COLLECTION = "outlet_states"

    def __init__(self, database: Database):
        self._db = database
        self._commands = database[self.COMMANDS_COLLECTION]
        self._states = database[self.STATES_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes."""
        self._commands.create_index(
            [("outlet_id", ASCENDING), ("timestamp", DESCENDING)],
            name="outlet_timestamp_idx"
        )
        self._states.create_index(
            "outlet_id",
            unique=True,
            name="outlet_id_idx"
        )

    def save_command(self, command: OutletCommand) -> bool:
        """Save an outlet command to the audit trail."""
        doc = {
            "command_id": command.command_id,
            "outlet_id": command.outlet_id,
            "desired_state": command.desired_state.value,
            "reason": command.reason,
            "triggered_by_sensor": command.triggered_by_sensor,
            "triggered_by_user": command.triggered_by_user,
            "timestamp": command.timestamp,
            "executed": command.executed,
            "execution_result": command.execution_result
        }
        result = self._commands.insert_one(doc)
        return result.acknowledged

    def get_command_history(
        self,
        outlet_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[OutletCommand]:
        """Get command history for an outlet."""
        cursor = self._commands.find({
            "outlet_id": outlet_id,
            "timestamp": {"$gte": start_time, "$lte": end_time}
        }).sort("timestamp", ASCENDING)

        return [self._doc_to_command(doc) for doc in cursor]

    def get_current_state(self, outlet_id: str) -> Optional[OutletState]:
        """Get the current state of an outlet."""
        doc = self._states.find_one({"outlet_id": outlet_id})
        return self._doc_to_state(doc) if doc else None

    def save_state(self, state: OutletState) -> bool:
        """Update the current state of an outlet."""
        doc = {
            "outlet_id": state.outlet_id,
            "state": state.state.value,
            "last_changed": state.last_changed,
            "mode": state.mode.value,
            "power_watts": state.power_watts
        }
        result = self._states.update_one(
            {"outlet_id": state.outlet_id},
            {"$set": doc},
            upsert=True
        )
        return result.acknowledged

    @staticmethod
    def _doc_to_command(doc: dict) -> OutletCommand:
        """Convert MongoDB document to OutletCommand."""
        return OutletCommand(
            command_id=doc["command_id"],
            outlet_id=doc["outlet_id"],
            desired_state=OutletStateEnum(doc["desired_state"]),
            reason=doc["reason"],
            triggered_by_sensor=doc.get("triggered_by_sensor"),
            triggered_by_user=doc.get("triggered_by_user"),
            timestamp=doc["timestamp"],
            executed=doc.get("executed", False),
            execution_result=doc.get("execution_result")
        )

    @staticmethod
    def _doc_to_state(doc: dict) -> OutletState:
        """Convert MongoDB document to OutletState."""
        return OutletState(
            outlet_id=doc["outlet_id"],
            state=OutletStateEnum(doc["state"]),
            last_changed=doc["last_changed"],
            mode=ControlMode(doc.get("mode", "automatic")),
            power_watts=doc.get("power_watts")
        )


class MongoDBHabitatRepository(HabitatRepository):
    """
    MongoDB adapter for storing habitat configurations.

    Collections:
        - habitats: Habitat configurations
        - habitat_requirements: Species requirements (pre-seeded)
    """

    HABITATS_COLLECTION = "habitats"
    REQUIREMENTS_COLLECTION = "habitat_requirements"

    def __init__(self, database: Database):
        self._db = database
        self._habitats = database[self.HABITATS_COLLECTION]
        self._requirements = database[self.REQUIREMENTS_COLLECTION]
        self._ensure_indexes()
        self._seed_requirements()

    def _ensure_indexes(self):
        """Create necessary indexes."""
        self._habitats.create_index("habitat_id", unique=True, name="habitat_id_idx")
        self._requirements.create_index("species", unique=True, name="species_idx")

    def _seed_requirements(self):
        """Pre-seed species requirements if they don't exist."""
        if self._requirements.count_documents({}) > 0:
            return  # Already seeded

        print("  Seeding species requirements...")
        requirements_data = [
            {
                "species": ReptileSpecies.BEARDED_DRAGON.value,
                "basking_temp_min": 35.0,
                "basking_temp_max": 40.0,
                "cool_side_temp_min": 24.0,
                "cool_side_temp_max": 29.0,
                "night_temp_min": 20.0,
                "night_temp_max": 24.0,
                "humidity_min": 30.0,
                "humidity_max": 40.0,
                "uv_required": True,
                "substrate_type": "tile or paper",
                "notes": "Desert species, needs hot basking spot"
            },
            {
                "species": ReptileSpecies.BALL_PYTHON.value,
                "basking_temp_min": 31.0,
                "basking_temp_max": 33.0,
                "cool_side_temp_min": 26.0,
                "cool_side_temp_max": 28.0,
                "night_temp_min": 24.0,
                "night_temp_max": 26.0,
                "humidity_min": 50.0,
                "humidity_max": 60.0,
                "uv_required": False,
                "substrate_type": "cypress mulch",
                "notes": "Tropical species, needs higher humidity"
            },
            {
                "species": ReptileSpecies.CORN_SNAKE.value,
                "basking_temp_min": 28.0,
                "basking_temp_max": 32.0,
                "cool_side_temp_min": 21.0,
                "cool_side_temp_max": 24.0,
                "night_temp_min": 20.0,
                "night_temp_max": 23.0,
                "humidity_min": 40.0,
                "humidity_max": 50.0,
                "uv_required": False,
                "substrate_type": "aspen shavings",
                "notes": "Hardy species, moderate temps"
            },
            {
                "species": ReptileSpecies.LEOPARD_GECKO.value,
                "basking_temp_min": 32.0,
                "basking_temp_max": 35.0,
                "cool_side_temp_min": 24.0,
                "cool_side_temp_max": 27.0,
                "night_temp_min": 21.0,
                "night_temp_max": 24.0,
                "humidity_min": 30.0,
                "humidity_max": 40.0,
                "uv_required": False,
                "substrate_type": "tile or paper",
                "notes": "Desert species, use heat mat for belly heat"
            }
        ]
        self._requirements.insert_many(requirements_data)
        print(f"  Seeded {len(requirements_data)} species requirements")

    def get_requirements(self, species: ReptileSpecies) -> HabitatRequirements:
        """Load species requirements from MongoDB."""
        doc = self._requirements.find_one({"species": species.value})
        if not doc:
            raise ValueError(f"No requirements found for {species.value}")
        return self._doc_to_requirements(doc)

    def get_habitat(self, habitat_id: str) -> Optional[Habitat]:
        """Load a habitat configuration."""
        doc = self._habitats.find_one({"habitat_id": habitat_id})
        if not doc:
            return None
        return self._doc_to_habitat(doc)

    def save_habitat(self, habitat: Habitat) -> bool:
        """Save a habitat configuration."""
        doc = self._habitat_to_doc(habitat)
        result = self._habitats.update_one(
            {"habitat_id": habitat.habitat_id},
            {"$set": doc},
            upsert=True
        )
        print(f"  Saved habitat: {habitat.name}")
        return result.acknowledged

    def list_habitats(self) -> List[Habitat]:
        """Get all habitat configurations."""
        cursor = self._habitats.find({})
        return [self._doc_to_habitat(doc) for doc in cursor]

    def _doc_to_requirements(self, doc: dict) -> HabitatRequirements:
        """Convert MongoDB document to HabitatRequirements."""
        return HabitatRequirements(
            species=ReptileSpecies(doc["species"]),
            basking_temp_min=doc["basking_temp_min"],
            basking_temp_max=doc["basking_temp_max"],
            cool_side_temp_min=doc["cool_side_temp_min"],
            cool_side_temp_max=doc["cool_side_temp_max"],
            night_temp_min=doc["night_temp_min"],
            night_temp_max=doc["night_temp_max"],
            humidity_min=doc["humidity_min"],
            humidity_max=doc["humidity_max"],
            uvb_required=doc.get("uv_required", False),
            substrate_type=doc.get("substrate_type"),
            notes=doc.get("notes")
        )

    def _doc_to_habitat(self, doc: dict) -> Habitat:
        """Convert MongoDB document to Habitat."""
        # Load the requirements for this species
        requirements = self.get_requirements(ReptileSpecies(doc["species"]))

        # Parse embedded sensors config
        sensors = []
        for sensor_doc in doc.get("sensors", []):
            sensors.append(SensorConfig(
                sensor_id=sensor_doc["sensor_id"],
                ble_address=sensor_doc["ble_address"],
                location=SensorLocation(sensor_doc["location"]),
                device_type=sensor_doc.get("device_type", "LYWSD03MMC")
            ))

        # Parse embedded power_strip config
        power_strip = None
        if doc.get("power_strip"):
            ps_doc = doc["power_strip"]
            outlets = []
            for outlet_doc in ps_doc.get("outlets", []):
                outlets.append(OutletConfig(
                    outlet_id=outlet_doc["outlet_id"],
                    plug_number=outlet_doc["plug_number"]
                ))
            power_strip = PowerStripConfig(
                strip_id=ps_doc["strip_id"],
                ip=ps_doc["ip"],
                username=ps_doc["username"],
                password=ps_doc["password"],
                outlets=outlets
            )

        return Habitat(
            habitat_id=doc["habitat_id"],
            name=doc["name"],
            species=ReptileSpecies(doc["species"]),
            requirements=requirements,
            sensors=sensors,
            power_strip=power_strip,
            basking_temp_sensor_id=doc.get("basking_temp_sensor_id", ""),
            cool_temp_sensor_id=doc.get("cool_temp_sensor_id", ""),
            humidity_sensor_id=doc.get("humidity_sensor_id", ""),
            heat_lamp_outlet_id=doc.get("heat_lamp_outlet_id", ""),
            ceramic_heater_outlet_id=doc.get("ceramic_heater_outlet_id"),
            uvb_outlet_id=doc.get("uvb_outlet_id"),
            humidifier_outlet_id=doc.get("humidifier_outlet_id"),
            mister_outlet_id=doc.get("mister_outlet_id")
        )

    @staticmethod
    def _habitat_to_doc(habitat: Habitat) -> dict:
        """Convert Habitat to MongoDB document."""
        # Convert sensors to embedded documents
        sensors_docs = []
        for sensor in habitat.sensors:
            sensors_docs.append({
                "sensor_id": sensor.sensor_id,
                "ble_address": sensor.ble_address,
                "location": sensor.location.value,
                "device_type": sensor.device_type
            })

        # Convert power_strip to embedded document
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

        return {
            "habitat_id": habitat.habitat_id,
            "name": habitat.name,
            "species": habitat.species.value,
            "sensors": sensors_docs,
            "power_strip": power_strip_doc,
            "basking_temp_sensor_id": habitat.basking_temp_sensor_id,
            "cool_temp_sensor_id": habitat.cool_temp_sensor_id,
            "humidity_sensor_id": habitat.humidity_sensor_id,
            "heat_lamp_outlet_id": habitat.heat_lamp_outlet_id,
            "ceramic_heater_outlet_id": habitat.ceramic_heater_outlet_id,
            "uvb_outlet_id": habitat.uvb_outlet_id,
            "humidifier_outlet_id": habitat.humidifier_outlet_id,
            "mister_outlet_id": habitat.mister_outlet_id
        }


class MongoDBThresholdRepository(ThresholdRepository):
    """
    MongoDB adapter for storing threshold configurations.

    Collection: thresholds
    """

    COLLECTION_NAME = "thresholds"

    def __init__(self, database: Database):
        self._db = database
        self._collection = database[self.COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self):
        """Create necessary indexes."""
        self._collection.create_index("sensor_id", unique=True, name="sensor_id_idx")

    def get_threshold(self, sensor_id: str) -> Optional[Threshold]:
        """Get threshold for a sensor."""
        doc = self._collection.find_one({"sensor_id": sensor_id})
        return self._doc_to_threshold(doc) if doc else None

    def save_threshold(self, threshold: Threshold) -> bool:
        """Save a threshold configuration."""
        doc = {
            "sensor_id": threshold.sensor_id,
            "zone_type": threshold.zone_type,
            "min_value": threshold.min_value,
            "max_value": threshold.max_value,
            "warning_min": threshold.warning_min,
            "warning_max": threshold.warning_max,
            "hysteresis": threshold.hysteresis
        }
        result = self._collection.update_one(
            {"sensor_id": threshold.sensor_id},
            {"$set": doc},
            upsert=True
        )
        print(f"  Saved threshold for {threshold.sensor_id}: {threshold.min_value}-{threshold.max_value}")
        return result.acknowledged

    def get_thresholds_by_habitat(self, habitat_id: str) -> List[Threshold]:
        """Get all thresholds (simplified - returns all)."""
        cursor = self._collection.find({})
        return [self._doc_to_threshold(doc) for doc in cursor]

    @staticmethod
    def _doc_to_threshold(doc: dict) -> Threshold:
        """Convert MongoDB document to Threshold."""
        return Threshold(
            sensor_id=doc["sensor_id"],
            zone_type=doc["zone_type"],
            min_value=doc["min_value"],
            max_value=doc["max_value"],
            warning_min=doc.get("warning_min"),
            warning_max=doc.get("warning_max"),
            hysteresis=doc.get("hysteresis", 2.0)
        )
