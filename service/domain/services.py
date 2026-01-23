# domain/services.py

"""
Domain Services for Reptile Habitat Automation System

Services contain the business logic for:
- Monitoring sensor readings
- Controlling outlets based on automation rules
- Managing habitat configurations

Each service orchestrates workflows and uses ports to interact with
external systems (hardware, databases, notifications).
"""

from datetime import datetime, timedelta,timezone
from typing import List, Dict, Optional
from uuid import uuid4

from domain.models import (
    SensorReading,
    SensorUnit,
    SensorMetadata,
    Habitat,
    HabitatRequirements,
    ReptileSpecies,
    Threshold,
    AutomationRule,
    OutletState,
    OutletStateEnum,
    OutletCommand,
    Alert,
    AlertLevel,
    HabitatDayNightConfig,
    SensorConfig,
    SensorLocation,
    OutletConfig,
    PowerStripConfig
)

from domain.ports import (
    SensorRepository,
    SensorHardwareInterface,
    OutletController,
    OutletRepository,
    HabitatRepository,
    ThresholdRepository,
    NotificationService,
    TimeProvider,
    SunTimesProvider,
    Logger
)


# ═══════════════════════════════════════════════════════════════════
# SENSOR MONITORING SERVICE
# ═══════════════════════════════════════════════════════════════════

class SensorMonitoringService:

    """
    Service for processing and monitoring sensor readings.

    Responsibilities:
    - Process incoming sensor readings (temperature and humidity)
    - Validate readings are within plausible ranges
    - Save readings to database
    - Check readings against thresholds
    - Trigger automation when readings processed
    - Track sensor health
    """

    def __init__(
            self,
            sensor_repository: SensorRepository,
            threshold_repository: ThresholdRepository,
            automation_service: Optional['OutletAutomationService'] = None,
            notification_service: Optional[NotificationService] = None,
            time_provider: Optional[TimeProvider] = None,
            logger: Optional[Logger] = None
    ):
        """
        Initialize monitoring service with dependencies.

        Args:
            sensor_repository: Port for storing/retrieving sensor data
            threshold_repository: Port for loading thresholds
            automation_service: Service to trigger automation (injected to avoid circular dependency)
            notification_service: Port for sending alerts (optional)
            time_provider: Port for getting current time (optional, uses datetime if not provided)
            logger: Port for logging (optional, uses print if not provided)
        """
        self._sensor_repo = sensor_repository
        self._threshold_repo = threshold_repository
        self._automation_service = automation_service
        self._notifier = notification_service
        self._time_provider = time_provider
        self._logger = logger

        # Internal state - track sensor health
        self._sensor_health: Dict[str, datetime] = {}

    def process_reading(
            self,
            sensor_id: str,
            value: float,
            timestamp: Optional[datetime] = None,
            unit: Optional[SensorUnit] = None,
            habitat_id: Optional[str] = None
    ) -> SensorReading:
        """
        Main business logic: Process a sensor reading.

        Workflow:
        1. Create reading object
        2. Validate it
        3. Save to database
        4. Check thresholds and send alerts
        5. Trigger automation
        6. Update sensor health

        Args:
            sensor_id: Unique identifier for the sensor
            value: The measured value
            timestamp: When reading was taken (uses current time if not provided)
            unit: Unit of measurement (CELSIUS or PERCENT)
            habitat_id: Optional habitat this reading belongs to

        Returns:
            SensorReading object with validation status
        """
        # Use current time if not provided
        if timestamp is None:
            timestamp = self._get_current_time()

        # Default to CELSIUS if not specified
        if unit is None:
            unit = SensorUnit.CELSIUS

        # Create domain model
        reading = SensorReading(
            sensor_id=sensor_id,
            value=value,
            timestamp=timestamp,
            unit=unit,
            is_valid=True,
            habitat_id=habitat_id
        )

        # Log processing
        self._log_info(f"Processing reading from {sensor_id}: {value}{unit.value}")

        # Validate reading (business logic)
        if not self._is_valid_reading(reading):
            reading.is_valid = False
            self._log_warning(
                f"Invalid reading from {sensor_id}",
                {"value": value, "unit": unit.value}
            )

        # Save reading to database (use port)
        try:
            saved = self._sensor_repo.save_reading(reading)
            if not saved:
                self._log_error(f"Failed to save reading for {sensor_id}")
        except Exception as e:
            self._log_error(f"Error saving reading for {sensor_id}", exception=e)

        # Check thresholds and send alerts if violated
        if reading.is_valid:
            alert = self._check_thresholds(reading)
            if alert and self._notifier:
                try:
                    self._notifier.send_alert(alert)
                    self._log_info(f"Alert sent for {sensor_id}: {alert.message}")
                except Exception as e:
                    self._log_error(f"Failed to send alert for {sensor_id}", exception=e)

        # Trigger automation if service is connected
        if self._automation_service and reading.is_valid:
            try:
                commands = self._automation_service.process_sensor_reading(reading)
                if commands:
                    self._log_info(
                        f"Automation triggered {len(commands)} command(s)",
                        {"sensor": sensor_id, "value": value}
                    )
            except Exception as e:
                self._log_error(f"Error in automation for {sensor_id}", exception=e)

        # Update sensor health tracking
        self._sensor_health[sensor_id] = timestamp

        return reading

    def get_sensor_status(self, sensor_id: str) -> dict:
        """
        Get current status of a sensor.

        Returns dict with:
        - sensor_id
        - latest_value
        - latest_timestamp
        - is_stale (hasn't reported recently)
        - threshold_status (ok, too_low, too_high)
        - threshold_info
        """
        # Get latest reading (use port)
        latest = self._sensor_repo.get_latest_reading(sensor_id)

        if not latest:
            return {
                "sensor_id": sensor_id,
                "status": "no_data",
                "latest_value": None,
                "latest_timestamp": None,
                "is_stale": True,
                "threshold_status": "unknown"
            }

        # Check if stale (no reading in last 5 minutes)
        current_time = self._get_current_time()
        age_seconds = (current_time - latest.timestamp).total_seconds()
        is_stale = age_seconds > 300  # 5 minutes

        # Get threshold (use port)
        threshold = self._threshold_repo.get_threshold(sensor_id)

        # Determine threshold status
        threshold_status = "ok"
        if threshold and latest.is_valid:
            if latest.value < threshold.min_value:
                threshold_status = "too_low"
            elif latest.value > threshold.max_value:
                threshold_status = "too_high"

        return {
            "sensor_id": sensor_id,
            "status": "stale" if is_stale else "active",
            "latest_value": latest.value,
            "latest_timestamp": latest.timestamp,
            "is_valid": latest.is_valid,
            "is_stale": is_stale,
            "threshold_status": threshold_status,
            "threshold": {
                "min": threshold.min_value if threshold else None,
                "max": threshold.max_value if threshold else None,
                "zone_type": threshold.zone_type if threshold else None
            } if threshold else None
        }

    def get_recent_readings(
            self,
            sensor_id: str,
            hours: int = 24
    ) -> List[SensorReading]:
        """
        Get recent readings for analysis.

        Args:
            sensor_id: Sensor to get readings for
            hours: How many hours back to retrieve

        Returns:
            List of SensorReading objects
        """
        end_time = self._get_current_time()
        start_time = end_time - timedelta(hours=hours)

        try:
            readings = self._sensor_repo.get_readings(sensor_id, start_time, end_time)
            return readings
        except Exception as e:
            self._log_error(f"Error getting readings for {sensor_id}", exception=e)
            return []

    # ============ PRIVATE HELPER METHODS ============

    def _is_valid_reading(self, reading: SensorReading) -> bool:
        """
        Business rule: Validate sensor reading.

        Checks:
        - Not NaN
        - Within physically possible range for the unit type
        """
        # Check for NaN
        if reading.value != reading.value:
            return False

        # Check range based on unit
        if reading.unit == SensorUnit.CELSIUS:
            # Temperature: -50°C to 100°C is physically reasonable
            if reading.value < -50 or reading.value > 100:
                return False
        elif reading.unit == SensorUnit.FAHRENHEIT:
            # Temperature: -58°F to 212°F
            if reading.value < -58 or reading.value > 212:
                return False
        elif reading.unit == SensorUnit.PERCENT:
            # Humidity: 0-100%
            if reading.value < 0 or reading.value > 100:
                return False

        return True

    def _check_thresholds(self, reading: SensorReading) -> Optional[Alert]:
        """
        Business logic: Check if reading violates thresholds.

        Returns Alert if threshold violated, None otherwise.
        """
        # Get threshold configuration (use port)
        threshold = self._threshold_repo.get_threshold(reading.sensor_id)

        if not threshold:
            return None  # No threshold configured

        # Check critical thresholds
        if reading.value < threshold.min_value:
            return Alert(
                alert_id=str(uuid4()),
                sensor_id=reading.sensor_id,
                severity=AlertLevel.CRITICAL,
                message=f"{reading.sensor_id} critically low: {reading.value}{reading.unit.value} < {threshold.min_value}{reading.unit.value}",
                value=reading.value,
                threshold_violated=f"min: {threshold.min_value}",
                created_at=self._get_current_time()
            )

        if reading.value > threshold.max_value:
            return Alert(
                alert_id=str(uuid4()),
                sensor_id=reading.sensor_id,
                severity=AlertLevel.CRITICAL,
                message=f"{reading.sensor_id} critically high: {reading.value}{reading.unit.value} > {threshold.max_value}{reading.unit.value}",
                value=reading.value,
                threshold_violated=f"max: {threshold.max_value}",
                created_at=self._get_current_time()
            )

        # Check warning thresholds
        if threshold.warning_min and reading.value < threshold.warning_min:
            return Alert(
                alert_id=str(uuid4()),
                sensor_id=reading.sensor_id,
                severity=AlertLevel.WARNING,
                message=f"{reading.sensor_id} approaching low limit: {reading.value}{reading.unit.value}",
                value=reading.value,
                threshold_violated=f"warning_min: {threshold.warning_min}",
                created_at=self._get_current_time()
            )

        if threshold.warning_max and reading.value > threshold.warning_max:
            return Alert(
                alert_id=str(uuid4()),
                sensor_id=reading.sensor_id,
                severity=AlertLevel.WARNING,
                message=f"{reading.sensor_id} approaching high limit: {reading.value}{reading.unit.value}",
                value=reading.value,
                threshold_violated=f"warning_max: {threshold.warning_max}",
                created_at=self._get_current_time()
            )

        return None  # No violation

    def _get_current_time(self) -> datetime:
        """Get current time (use time provider if available, otherwise datetime)"""
        if self._time_provider:
            return self._time_provider.now()
        from datetime import timezone
        return datetime.now(timezone.utc)

    def _log_info(self, message: str, context: dict = None):
        """Log info message"""
        if self._logger:
            self._logger.info(message, context)
        else:
            print(f"[INFO] {message}")

    def _log_warning(self, message: str, context: dict = None):
        """Log warning message"""
        if self._logger:
            self._logger.warning(message, context)
        else:
            print(f"[WARNING] {message}")

    def _log_error(self, message: str, context: dict = None, exception: Exception = None):
        """Log error message"""
        if self._logger:
            self._logger.error(message, context, exception)
        else:
            print(f"[ERROR] {message}")
            if exception:
                print(f"  Exception: {exception}")


# ═══════════════════════════════════════════════════════════════════
# OUTLET AUTOMATION SERVICE
# ═══════════════════════════════════════════════════════════════════

class OutletAutomationService:
    """
    Service for controlling outlets based on automation rules.

    Responsibilities:
    - Register and manage automation rules
    - Evaluate rules when sensor readings arrive
    - Execute outlet commands
    - Track command history
    - Respect cooldown periods to prevent rapid cycling
    """

    def __init__(
            self,
            outlet_controller: OutletController,
            outlet_repository: OutletRepository,
            time_provider: Optional[TimeProvider] = None,
            logger: Optional[Logger] = None
    ):
        """
        Initialize automation service with dependencies.

        Args:
            outlet_controller: Port for controlling physical outlets
            outlet_repository: Port for storing command history
            time_provider: Port for getting current time (optional)
            logger: Port for logging (optional)
        """
        self._outlet_controller = outlet_controller
        self._outlet_repo = outlet_repository
        self._time_provider = time_provider
        self._logger = logger

        # Internal state - store active rules
        self._rules: Dict[str, AutomationRule] = {}

    def register_rule(self, rule: AutomationRule) -> None:
        """
        Register an automation rule.

        Business logic: Add rule to active rules collection.
        """
        self._rules[rule.rule_id] = rule
        self._log_info(
            f"Registered automation rule: {rule.name}",
            {
                "rule_id": rule.rule_id,
                "sensor": rule.sensor_id,
                "outlet": rule.outlet_id,
                "trigger": f"{rule.trigger_operator} {rule.trigger_value}"
            }
        )

    def unregister_rule(self, rule_id: str) -> bool:
        """Remove a rule from active rules"""
        if rule_id in self._rules:
            rule = self._rules.pop(rule_id)
            self._log_info(f"Unregistered rule: {rule.name}")
            return True
        return False

    def disable_rule(self, rule_id: str) -> bool:
        """Temporarily disable a rule without removing it"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = False
            self._log_info(f"Disabled rule: {rule_id}")
            return True
        return False

    def enable_rule(self, rule_id: str) -> bool:
        """Re-enable a disabled rule"""
        if rule_id in self._rules:
            self._rules[rule_id].enabled = True
            self._log_info(f"Enabled rule: {rule_id}")
            return True
        return False

    def process_sensor_reading(
            self,
            reading: SensorReading
    ) -> List[OutletCommand]:
        """
        Main business logic: Check if sensor reading triggers any rules.

        Workflow:
        1. Find all rules for this sensor
        2. Check each rule to see if it should trigger
        3. Execute triggered rules
        4. Return list of commands that were executed

        Args:
            reading: The sensor reading to process

        Returns:
            List of OutletCommand objects that were executed
        """
        commands_executed = []

        # Find applicable rules for this sensor
        applicable_rules = self._find_rules_for_sensor(reading.sensor_id)

        if not applicable_rules:
            return commands_executed

        # Check each rule
        for rule in applicable_rules:
            # Use rule's domain logic to check if it should trigger
            if rule.should_trigger(reading.value):
                # Check if enough time has passed since last trigger (cooldown)
                if not self._can_trigger_rule(rule):
                    self._log_info(
                        f"Rule '{rule.name}' in cooldown period",
                        {"seconds_since_last": self._seconds_since_trigger(rule)}
                    )
                    continue

                # Execute the rule
                command = self._execute_rule(rule, reading)
                if command:
                    commands_executed.append(command)

        return commands_executed

    def manual_control(
            self,
            outlet_id: str,
            desired_state: OutletStateEnum,
            user: str = "manual"
    ) -> OutletCommand:
        """
        Business logic: Manually control an outlet (override automation).

        Args:
            outlet_id: Which outlet to control
            desired_state: ON or OFF
            user: Who initiated the command

        Returns:
            OutletCommand that was executed
        """
        # Create command
        command = OutletCommand(
            command_id=str(uuid4()),
            outlet_id=outlet_id,
            desired_state=desired_state,
            reason="Manual control",
            triggered_by_user=user,
            timestamp=self._get_current_time(),
            executed=False
        )

        # Execute via port
        success = self._execute_outlet_command(command)
        command.executed = success
        command.execution_result = "success" if success else "failed"

        # Save to history via port
        try:
            self._outlet_repo.save_command(command)
        except Exception as e:
            self._log_error("Failed to save manual command", exception=e)

        self._log_info(
            f"Manual control: {outlet_id} → {desired_state.value}",
            {"user": user, "success": success}
        )

        return command

    def get_outlet_status(self, outlet_id: str) -> dict:
        """
        Get current status of an outlet.

        Returns dict with:
        - outlet_id
        - current_state (ON/OFF/UNKNOWN)
        - last_changed
        - applicable_rules (list of rules that control this outlet)
        """
        # Get current state from controller (use port)
        try:
            state = self._outlet_controller.get_state(outlet_id)
        except Exception as e:
            self._log_error(f"Error getting state for {outlet_id}", exception=e)
            state = OutletState(
                outlet_id=outlet_id,
                state=OutletStateEnum.ERROR,
                last_changed=self._get_current_time()
            )

        # Find rules that control this outlet
        applicable_rules = [
            {
                "rule_id": rule.rule_id,
                "name": rule.name,
                "sensor": rule.sensor_id,
                "enabled": rule.enabled,
                "trigger": f"{rule.trigger_operator} {rule.trigger_value}"
            }
            for rule in self._rules.values()
            if rule.outlet_id == outlet_id
        ]

        return {
            "outlet_id": outlet_id,
            "state": state.state.value,
            "last_changed": state.last_changed,
            "mode": state.mode.value if hasattr(state, 'mode') else "unknown",
            "power_watts": state.power_watts if hasattr(state, 'power_watts') else None,
            "rules": applicable_rules
        }

    def get_all_rules(self) -> List[AutomationRule]:
        """Get all registered rules"""
        return list(self._rules.values())

    # ============ PRIVATE HELPER METHODS ============

    def _find_rules_for_sensor(self, sensor_id: str) -> List[AutomationRule]:
        """Find all enabled rules that apply to this sensor"""
        return [
            rule for rule in self._rules.values()
            if rule.sensor_id == sensor_id and rule.enabled
        ]

    def _can_trigger_rule(self, rule: AutomationRule) -> bool:
        """
        Business logic: Check if enough time has passed since last trigger.
        Prevents rapid cycling of outlets.
        """
        if not rule.last_triggered:
            return True  # Never triggered before

        elapsed = self._seconds_since_trigger(rule)
        return elapsed >= rule.min_duration_seconds

    def _seconds_since_trigger(self, rule: AutomationRule) -> float:
        """Calculate seconds since rule last triggered"""
        if not rule.last_triggered:
            return float('inf')

        current_time = self._get_current_time()
        return (current_time - rule.last_triggered).total_seconds()

    def _execute_rule(
            self,
            rule: AutomationRule,
            reading: SensorReading
    ) -> Optional[OutletCommand]:
        """
        Execute an automation rule.

        Returns OutletCommand if executed, None if skipped.
        """
        # Business logic: Check if outlet is already in desired state
        try:
            current_state = self._outlet_controller.get_state(rule.outlet_id)
            if current_state.state == rule.action_on_trigger:
                self._log_info(
                    f"Outlet {rule.outlet_id} already in desired state {rule.action_on_trigger.value}"
                )
                return None
        except Exception as e:
            self._log_error(f"Error checking outlet state", exception=e)
            # Continue anyway - try to execute

        # Create command
        command = OutletCommand(
            command_id=str(uuid4()),
            outlet_id=rule.outlet_id,
            desired_state=rule.action_on_trigger,
            reason=f"Automation: {rule.name}",
            triggered_by_sensor=reading.sensor_id,
            timestamp=self._get_current_time(),
            executed=False
        )

        # Execute command
        success = self._execute_outlet_command(command)
        command.executed = success
        command.execution_result = "success" if success else "failed"

        # Save to history
        try:
            self._outlet_repo.save_command(command)
        except Exception as e:
            self._log_error("Failed to save automation command", exception=e)

        # Update rule state
        if success:
            rule.last_triggered = self._get_current_time()
            self._log_info(
                f"Automation executed: {rule.name}",
                {
                    "outlet": rule.outlet_id,
                    "action": rule.action_on_trigger.value,
                    "sensor_value": reading.value,
                    "trigger": f"{rule.trigger_operator} {rule.trigger_value}"
                }
            )

        return command

    def _execute_outlet_command(self, command: OutletCommand) -> bool:
        """
        Actually execute an outlet command via hardware.

        Returns True if successful, False otherwise.
        """
        try:
            if command.desired_state == OutletStateEnum.ON:
                return self._outlet_controller.turn_on(command.outlet_id)
            elif command.desired_state == OutletStateEnum.OFF:
                return self._outlet_controller.turn_off(command.outlet_id)
            else:
                self._log_error(f"Invalid outlet state: {command.desired_state}")
                return False
        except Exception as e:
            self._log_error(
                f"Error executing outlet command",
                exception=e,
                context={"outlet": command.outlet_id, "state": command.desired_state.value}
            )
            return False

    def _get_current_time(self) -> datetime:
        """Get current time (use time provider if available)"""
        if self._time_provider:
            return self._time_provider.now()
        from datetime import timezone
        return datetime.now(timezone.utc)

    def _log_info(self, message: str, context: dict = None):
        """Log info message"""
        if self._logger:
            self._logger.info(message, context)
        else:
            print(f"[INFO] {message}")

    def _log_error(self, message: str, context: dict = None, exception: Exception = None):
        """Log error message"""
        if self._logger:
            self._logger.error(message, context, exception)
        else:
            print(f"[ERROR] {message}")
            if exception:
                print(f"  Exception: {exception}")


# ═══════════════════════════════════════════════════════════════════
# HABITAT MANAGEMENT SERVICE
# ═══════════════════════════════════════════════════════════════════

class HabitatManagementService:
    """
    Service for setting up and managing reptile habitats.

    Responsibilities:
    - Load species requirements from database
    - Create habitat configurations
    - Generate thresholds from requirements
    - Create automation rules for each habitat
    - Provide habitat status overview
    """

    def __init__(
            self,
            habitat_repository: HabitatRepository,
            threshold_repository: ThresholdRepository,
            automation_service: OutletAutomationService,
            sensor_monitoring: SensorMonitoringService,
            logger: Optional[Logger] = None
    ):
        """
        Initialize habitat management service.

        Args:
            habitat_repository: Port for loading/saving habitat configs
            threshold_repository: Port for storing thresholds
            automation_service: Automation service to register rules with
            sensor_monitoring: Monitoring service for status checks
            logger: Port for logging (optional)
        """
        self._habitat_repo = habitat_repository
        self._threshold_repo = threshold_repository
        self._automation = automation_service
        self._monitoring = sensor_monitoring
        self._logger = logger

    def setup_habitat(
            self,
            habitat_id: str,
            name: str,
            species: ReptileSpecies,
            sensor_config: dict,
            outlet_config: dict,
            sensors: Optional[List[SensorConfig]] = None,
            power_strip: Optional[PowerStripConfig] = None
    ) -> Habitat:
        """
        Complete habitat setup workflow.

        This is the main business logic for creating a new habitat:
        1. Load species requirements from database
        2. Create habitat configuration
        3. Generate thresholds from requirements
        4. Create automation rules
        5. Register rules with automation service
        6. Save habitat configuration

        Args:
            habitat_id: Unique identifier for habitat
            name: Friendly name (e.g., "Fred's Tank")
            species: Species being housed
            sensor_config: Dict mapping zone types to sensor IDs
                          {'basking_temp': 'sensor-1', 'cool_temp': 'sensor-2', 'humidity': 'sensor-3'}
            outlet_config: Dict mapping equipment to outlet IDs
                          {'heat_lamp': 'outlet-1', 'humidifier': 'outlet-2'}
            sensors: Optional list of SensorConfig objects with BLE addresses
            power_strip: Optional PowerStripConfig with IP, credentials, and outlet mapping

        Returns:
            Habitat object with complete configuration
        """
        self._log_info(
            f"Setting up habitat: {name}",
            {"habitat_id": habitat_id, "species": species.value}
        )

        # 1. Load species requirements from database (use port)
        requirements = self._habitat_repo.get_requirements(species)

        self._log_info(
            f"Loaded requirements for {species.value}",
            {
                "basking": f"{requirements.basking_temp_min}-{requirements.basking_temp_max}°C",
                "humidity": f"{requirements.humidity_min}-{requirements.humidity_max}%"
            }
        )

        # 2. Create habitat model with embedded hardware config
        habitat = Habitat(
            habitat_id=habitat_id,
            name=name,
            species=species,
            requirements=requirements,
            sensors=sensors or [],
            power_strip=power_strip,
            basking_temp_sensor_id=sensor_config.get('basking_temp', ''),
            cool_temp_sensor_id=sensor_config.get('cool_temp', ''),
            humidity_sensor_id=sensor_config.get('humidity', ''),
            heat_lamp_outlet_id=outlet_config.get('heat_lamp', ''),
            ceramic_heater_outlet_id=outlet_config.get('ceramic_heater'),
            uvb_outlet_id=outlet_config.get('uvb'),
            humidifier_outlet_id=outlet_config.get('humidifier'),
            mister_outlet_id=outlet_config.get('mister')
        )

        # 3. Create thresholds from requirements
        all_rules = []

        # Basking zone thresholds and rules
        if habitat.basking_temp_sensor_id and habitat.heat_lamp_outlet_id:
            basking_threshold = Threshold.from_habitat_requirements(
                sensor_id=habitat.basking_temp_sensor_id,
                zone_type="basking",
                requirements=requirements
            )

            # Save threshold
            self._threshold_repo.save_threshold(basking_threshold)

            # Create automation rules (ON when cold, OFF when hot)
            basking_rules = basking_threshold.create_heating_rules(
                habitat_id=habitat_id,
                outlet_id=habitat.heat_lamp_outlet_id
            )
            all_rules.extend(basking_rules)

        # Cool side thresholds and rules
        if habitat.cool_temp_sensor_id and habitat.ceramic_heater_outlet_id:
            cool_threshold = Threshold.from_habitat_requirements(
                sensor_id=habitat.cool_temp_sensor_id,
                zone_type="cool_side",
                requirements=requirements
            )

            self._threshold_repo.save_threshold(cool_threshold)

            cool_rules = cool_threshold.create_heating_rules(
                habitat_id=habitat_id,
                outlet_id=habitat.ceramic_heater_outlet_id
            )
            all_rules.extend(cool_rules)

        # Humidity thresholds and rules
        if habitat.humidity_sensor_id and habitat.humidifier_outlet_id:
            humidity_threshold = Threshold.from_habitat_requirements(
                sensor_id=habitat.humidity_sensor_id,
                zone_type="humidity",
                requirements=requirements
            )

            self._threshold_repo.save_threshold(humidity_threshold)

            humidity_rules = humidity_threshold.create_humidity_rules(
                habitat_id=habitat_id,
                outlet_id=habitat.humidifier_outlet_id
            )
            all_rules.extend(humidity_rules)

        # 4. Register all automation rules
        for rule in all_rules:
            self._automation.register_rule(rule)

        self._log_info(
            f"Created {len(all_rules)} automation rules for {name}",
            {"habitat_id": habitat_id}
        )

        # 5. Save habitat configuration (use port)
        try:
            self._habitat_repo.save_habitat(habitat)
        except Exception as e:
            self._log_error(f"Failed to save habitat {habitat_id}", exception=e)

        self._log_info(
            f"✅ Habitat '{name}' configured successfully",
            {
                "species": species.value,
                "basking_range": f"{requirements.basking_temp_min}-{requirements.basking_temp_max}°C",
                "humidity_range": f"{requirements.humidity_min}-{requirements.humidity_max}%"
            }
        )

        return habitat

    def get_habitat_status(self, habitat_id: str) -> dict:
        """
        Get comprehensive status of a habitat.

        Returns dict with:
        - habitat_id, name, species
        - current_conditions (temp, humidity)
        - ideal_conditions (ranges)
        - status (whether in ideal range)
        - outlet_states
        - recent_alerts
        """
        # Load habitat (use port)
        habitat = self._habitat_repo.get_habitat(habitat_id)

        if not habitat:
            return {
                "habitat_id": habitat_id,
                "error": "Habitat not found"
            }

        # Get current sensor readings
        basking_status = self._monitoring.get_sensor_status(habitat.basking_temp_sensor_id)
        cool_status = self._monitoring.get_sensor_status(habitat.cool_temp_sensor_id)
        humidity_status = self._monitoring.get_sensor_status(habitat.humidity_sensor_id)

        # Get outlet states
        outlets = {}
        if habitat.heat_lamp_outlet_id:
            outlets['heat_lamp'] = self._automation.get_outlet_status(habitat.heat_lamp_outlet_id)
        if habitat.humidifier_outlet_id:
            outlets['humidifier'] = self._automation.get_outlet_status(habitat.humidifier_outlet_id)

        # Determine overall status
        reqs = habitat.requirements
        overall_ok = True

        if basking_status['latest_value']:
            basking_ok = (reqs.basking_temp_min <= basking_status['latest_value'] <= reqs.basking_temp_max)
            overall_ok = overall_ok and basking_ok

        if humidity_status['latest_value']:
            humidity_ok = (reqs.humidity_min <= humidity_status['latest_value'] <= reqs.humidity_max)
            overall_ok = overall_ok and humidity_ok

        return {
            "habitat_id": habitat_id,
            "name": habitat.name,
            "species": habitat.species.value,
            "current_conditions": {
                "basking_temp": basking_status['latest_value'],
                "cool_temp": cool_status['latest_value'],
                "humidity": humidity_status['latest_value']
            },
            "ideal_conditions": {
                "basking_temp": f"{reqs.basking_temp_min}-{reqs.basking_temp_max}°C",
                "cool_temp": f"{reqs.cool_side_temp_min}-{reqs.cool_side_temp_max}°C",
                "humidity": f"{reqs.humidity_min}-{reqs.humidity_max}%"
            },
            "sensor_status": {
                "basking_temp": basking_status['threshold_status'],
                "cool_temp": cool_status['threshold_status'],
                "humidity": humidity_status['threshold_status']
            },
            "outlets": outlets,
            "overall_status": "ok" if overall_ok else "out_of_range"
        }

    def update_requirements(
            self,
            habitat_id: str,
            requirements: HabitatRequirements
    ) -> Habitat:
        """
        Update requirements for an existing habitat.
        This will regenerate thresholds and automation rules.
        """
        # Load existing habitat
        habitat = self._habitat_repo.get_habitat(habitat_id)

        if not habitat:
            raise ValueError(f"Habitat {habitat_id} not found")

        # Update requirements
        habitat.requirements = requirements

        # TODO: Regenerate thresholds and rules
        # This would require unregistering old rules and creating new ones

        # Save updated habitat
        self._habitat_repo.save_habitat(habitat)

        self._log_info(f"Updated requirements for habitat {habitat_id}")

        return habitat

    def list_all_habitats(self) -> List[Habitat]:
        """Get all configured habitats"""
        try:
            return self._habitat_repo.list_habitats()
        except Exception as e:
            self._log_error("Error listing habitats", exception=e)
            return []

    # ============ PRIVATE HELPER METHODS ============

    def _log_info(self, message: str, context: dict = None):
        """Log info message"""
        if self._logger:
            self._logger.info(message, context)
        else:
            print(f"[INFO] {message}")

    def _log_error(self, message: str, context: dict = None, exception: Exception = None):
        """Log error message"""
        if self._logger:
            self._logger.error(message, context, exception)
        else:
            print(f"[ERROR] {message}")
            if exception:
                print(f"  Exception: {exception}")


# ═══════════════════════════════════════════════════════════════════
# SENSOR POLLING SERVICE (Optional - can be in main.py instead)
# ═══════════════════════════════════════════════════════════════════

class SensorPollingService:
    """
    Service for actively polling sensors on a schedule.

    This could also just be a loop in main.py - it's here if you want
    to encapsulate the polling logic.

    Responsibilities:
    - Read from sensor hardware on schedule
    - Call SensorMonitoringService with readings
    - Handle sensor failures gracefully
    """

    def __init__(
            self,
            sensor_interface: SensorHardwareInterface,
            monitoring_service: SensorMonitoringService,
            temp_sensor_id: str,
            humidity_sensor_id: str,
            logger: Optional[Logger] = None
    ):
        """
        Initialize polling service.

        Args:
            sensor_interface: Port for reading from hardware
            monitoring_service: Service to process readings
            temp_sensor_id: ID for temperature readings
            humidity_sensor_id: ID for humidity readings
            logger: Port for logging (optional)
        """
        self._sensor = sensor_interface
        self._monitoring = monitoring_service
        self._temp_sensor_id = temp_sensor_id
        self._humidity_sensor_id = humidity_sensor_id
        self._logger = logger

    def poll_once(self) -> tuple[Optional[SensorReading], Optional[SensorReading]]:
        """
        Poll sensor once and process readings.

        Returns:
            Tuple of (temperature_reading, humidity_reading)
            Either can be None if reading failed
        """
        try:
            # Check if sensor is healthy
            if not self._sensor.is_healthy():
                self._log_error("Sensor not healthy")
                return (None, None)

            # Read from sensor (OUTBOUND PORT CALL)
            temperature, humidity = self._sensor.read_temperature_and_humidity()

            # Get current time
            from datetime import timezone
            timestamp = datetime.now(timezone.utc)

            # Process temperature reading
            temp_reading = self._monitoring.process_reading(
                sensor_id=self._temp_sensor_id,
                value=temperature,
                timestamp=timestamp,
                unit=SensorUnit.CELSIUS
            )

            # Process humidity reading
            humidity_reading = self._monitoring.process_reading(
                sensor_id=self._humidity_sensor_id,
                value=humidity,
                timestamp=timestamp,
                unit=SensorUnit.PERCENT
            )

            return (temp_reading, humidity_reading)

        except Exception as e:
            self._log_error("Error polling sensor", exception=e)
            return (None, None)

    def poll_continuously(self, interval_seconds: int = 60):
        """
        Continuously poll sensor at specified interval.
        This is a blocking operation.

        Args:
            interval_seconds: How often to poll
        """
        import time

        self._log_info(f"Starting continuous polling (every {interval_seconds}s)")

        try:
            while True:
                temp_reading, humidity_reading = self.poll_once()

                if temp_reading and humidity_reading:
                    self._log_info(
                        f"Polled: {temp_reading.value}°C, {humidity_reading.value}%"
                    )

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self._log_info("Polling stopped by user")

    def _log_info(self, message: str):
        """Log info message"""
        if self._logger:
            self._logger.info(message)
        else:
            print(f"[INFO] {message}")

    def _log_error(self, message: str, exception: Exception = None):
        """Log error message"""
        if self._logger:
            self._logger.error(message, exception=exception)
        else:
            print(f"[ERROR] {message}")
            if exception:
                print(f"  Exception: {exception}")


# ═══════════════════════════════════════════════════════════════════
# DAY/NIGHT SERVICE
# ═══════════════════════════════════════════════════════════════════

class DayNightService:
    """
    Service for managing day/night transitions based on sunrise/sunset.

    Responsibilities:
    - Track current day/night state based on astronomical sunrise/sunset
    - Control UVB lights (on at sunrise, off at sunset)
    - Turn off all daytime heating at sunset
    - Enable night-time emergency heating (maintain night_temp_min to night_temp_max)
    - Coordinate with OutletAutomationService to enable/disable rules

    Day mode (sunrise to sunset):
    - UVB light: ON
    - Basking heat lamp: Controlled by daytime automation rules
    - Ceramic heater: Controlled by daytime automation rules

    Night mode (sunset to sunrise):
    - UVB light: OFF
    - Basking heat lamp: OFF (no heat from visible light at night)
    - Ceramic heater (CHE): Only if temp < night_temp_min, maintain night_temp_min-max
    """

    def __init__(
        self,
        outlet_controller: OutletController,
        automation_service: OutletAutomationService,
        sun_times_provider: SunTimesProvider,
        time_provider: Optional[TimeProvider] = None,
        logger: Optional[Logger] = None
    ):
        """
        Initialize the day/night service.

        Args:
            outlet_controller: Port for controlling physical outlets
            automation_service: Service to enable/disable automation rules
            sun_times_provider: Port for getting sunrise/sunset times
            time_provider: Port for getting current time (optional)
            logger: Port for logging (optional)
        """
        self._outlet_controller = outlet_controller
        self._automation = automation_service
        self._sun_times = sun_times_provider
        self._time_provider = time_provider
        self._logger = logger

        # Track current mode
        self._is_day_mode: Optional[bool] = None  # None = not yet determined
        self._last_mode_change: Optional[datetime] = None

        # Habitat configurations for day/night control
        # Maps habitat_id -> HabitatDayNightConfig
        self._habitat_configs: Dict[str, 'HabitatDayNightConfig'] = {}

        # Track night heating rules we've created
        self._night_heating_rules: Dict[str, List[str]] = {}  # habitat_id -> rule_ids

    def register_habitat(
        self,
        habitat: Habitat,
        daytime_heat_rule_ids: List[str]
    ) -> None:
        """
        Register a habitat for day/night management.

        Args:
            habitat: The Habitat object with outlet and sensor configs
            daytime_heat_rule_ids: IDs of automation rules to disable at night
        """
        config = HabitatDayNightConfig(
            habitat_id=habitat.habitat_id,
            uvb_outlet_id=habitat.uvb_outlet_id,
            heat_lamp_outlet_id=habitat.heat_lamp_outlet_id,
            ceramic_heater_outlet_id=habitat.ceramic_heater_outlet_id,
            cool_temp_sensor_id=habitat.cool_temp_sensor_id,
            night_temp_min=habitat.requirements.night_temp_min,
            night_temp_max=habitat.requirements.night_temp_max,
            daytime_heat_rule_ids=daytime_heat_rule_ids
        )
        self._habitat_configs[habitat.habitat_id] = config

        self._log_info(
            f"Registered habitat for day/night control: {habitat.habitat_id}",
            {
                "uvb_outlet": habitat.uvb_outlet_id,
                "heat_lamp_outlet": habitat.heat_lamp_outlet_id,
                "night_temp_range": f"{habitat.requirements.night_temp_min}-{habitat.requirements.night_temp_max}°C"
            }
        )

    def check_and_update(self) -> dict:
        """
        Check current time and update day/night mode if needed.

        This should be called periodically (e.g., every polling cycle).

        Returns:
            Dict with:
            - mode: "day" or "night"
            - mode_changed: True if mode just changed
            - sunrise: Today's sunrise time
            - sunset: Today's sunset time
            - actions_taken: List of actions performed
        """
        current_time = self._get_current_time()
        sunrise = self._sun_times.get_sunrise(current_time)
        sunset = self._sun_times.get_sunset(current_time)
        is_daytime = self._sun_times.is_daytime(current_time)

        actions_taken = []
        mode_changed = False

        # Check if mode needs to change
        if self._is_day_mode is None:
            # First run - initialize to current state
            self._is_day_mode = is_daytime
            self._last_mode_change = current_time
            mode_changed = True

            if is_daytime:
                actions_taken.extend(self._enter_day_mode(current_time))
            else:
                actions_taken.extend(self._enter_night_mode(current_time))

        elif is_daytime and not self._is_day_mode:
            # Transition: Night -> Day (sunrise)
            self._is_day_mode = True
            self._last_mode_change = current_time
            mode_changed = True
            actions_taken.extend(self._enter_day_mode(current_time))
            self._log_info(
                f"Day mode activated at sunrise",
                {"sunrise": sunrise.isoformat(), "time": current_time.isoformat()}
            )

        elif not is_daytime and self._is_day_mode:
            # Transition: Day -> Night (sunset)
            self._is_day_mode = False
            self._last_mode_change = current_time
            mode_changed = True
            actions_taken.extend(self._enter_night_mode(current_time))
            self._log_info(
                f"Night mode activated at sunset",
                {"sunset": sunset.isoformat(), "time": current_time.isoformat()}
            )

        return {
            "mode": "day" if self._is_day_mode else "night",
            "mode_changed": mode_changed,
            "sunrise": sunrise,
            "sunset": sunset,
            "current_time": current_time,
            "actions_taken": actions_taken
        }

    def get_status(self) -> dict:
        """Get current day/night status."""
        current_time = self._get_current_time()
        sunrise = self._sun_times.get_sunrise(current_time)
        sunset = self._sun_times.get_sunset(current_time)

        return {
            "mode": "day" if self._is_day_mode else "night",
            "is_day_mode": self._is_day_mode,
            "last_mode_change": self._last_mode_change,
            "sunrise": sunrise,
            "sunset": sunset,
            "current_time": current_time,
            "registered_habitats": list(self._habitat_configs.keys())
        }

    def get_sunrise(self, date: datetime = None) -> datetime:
        """Get sunrise time (convenience method)."""
        return self._sun_times.get_sunrise(date)

    def get_sunset(self, date: datetime = None) -> datetime:
        """Get sunset time (convenience method)."""
        return self._sun_times.get_sunset(date)

    def is_daytime(self) -> bool:
        """Check if it's currently daytime."""
        return self._is_day_mode if self._is_day_mode is not None else self._sun_times.is_daytime()

    def get_next_sun_event(self) -> tuple[datetime, str]:
        """
        Get the next sunrise or sunset event.

        Returns:
            Tuple of (event_time, event_type) where event_type is "sunrise" or "sunset"
        """
        current_time = self._get_current_time()
        today_sunrise = self._sun_times.get_sunrise(current_time)
        today_sunset = self._sun_times.get_sunset(current_time)

        # If we haven't passed today's sunrise yet, that's next
        if current_time < today_sunrise:
            return (today_sunrise, "sunrise")

        # If we haven't passed today's sunset yet, that's next
        if current_time < today_sunset:
            return (today_sunset, "sunset")

        # Both today's events have passed, get tomorrow's sunrise
        from datetime import timedelta
        tomorrow = current_time + timedelta(days=1)
        tomorrow_sunrise = self._sun_times.get_sunrise(tomorrow)
        return (tomorrow_sunrise, "sunrise")

    def seconds_until_next_sun_event(self) -> tuple[float, str]:
        """
        Get the number of seconds until the next sunrise or sunset.

        Returns:
            Tuple of (seconds, event_type) where event_type is "sunrise" or "sunset"
        """
        current_time = self._get_current_time()
        next_event, event_type = self.get_next_sun_event()
        seconds = (next_event - current_time).total_seconds()
        return (max(0, seconds), event_type)

    # ============ PRIVATE HELPER METHODS ============

    def _enter_day_mode(self, current_time: datetime) -> List[str]:
        """
        Transition to day mode.

        Actions:
        1. Turn on UVB lights
        2. Enable daytime heating rules
        3. Disable night heating rules
        4. Turn off night-only heaters (they'll be controlled by daytime rules)
        """
        actions = []

        for habitat_id, config in self._habitat_configs.items():
            # Turn on UVB
            if config.uvb_outlet_id:
                try:
                    self._outlet_controller.turn_on(config.uvb_outlet_id)
                    actions.append(f"UVB ON ({config.uvb_outlet_id})")
                except Exception as e:
                    self._log_error(f"Failed to turn on UVB for {habitat_id}", exception=e)

            # Enable daytime heating rules
            for rule_id in config.daytime_heat_rule_ids:
                self._automation.enable_rule(rule_id)
                actions.append(f"Enabled daytime rule: {rule_id}")

            # Disable night heating rules
            night_rule_ids = self._night_heating_rules.get(habitat_id, [])
            for rule_id in night_rule_ids:
                self._automation.disable_rule(rule_id)
                actions.append(f"Disabled night rule: {rule_id}")

        return actions

    def _enter_night_mode(self, current_time: datetime) -> List[str]:
        """
        Transition to night mode.

        Actions:
        1. Turn off UVB lights
        2. Turn off basking heat lamp (no visible light at night)
        3. Disable daytime heating rules
        4. Create and enable night heating rules (ceramic heater only, if temp < night_temp_min)
        """
        actions = []

        for habitat_id, config in self._habitat_configs.items():
            # Turn off UVB
            if config.uvb_outlet_id:
                try:
                    self._outlet_controller.turn_off(config.uvb_outlet_id)
                    actions.append(f"UVB OFF ({config.uvb_outlet_id})")
                except Exception as e:
                    self._log_error(f"Failed to turn off UVB for {habitat_id}", exception=e)

            # Turn off basking heat lamp (no visible light at night)
            if config.heat_lamp_outlet_id:
                try:
                    self._outlet_controller.turn_off(config.heat_lamp_outlet_id)
                    actions.append(f"Heat lamp OFF ({config.heat_lamp_outlet_id})")
                except Exception as e:
                    self._log_error(f"Failed to turn off heat lamp for {habitat_id}", exception=e)

            # Disable daytime heating rules
            for rule_id in config.daytime_heat_rule_ids:
                self._automation.disable_rule(rule_id)
                actions.append(f"Disabled daytime rule: {rule_id}")

            # Create/enable night heating rules for ceramic heater
            if config.ceramic_heater_outlet_id and config.cool_temp_sensor_id:
                night_rules = self._create_night_heating_rules(habitat_id, config)
                self._night_heating_rules[habitat_id] = [r.rule_id for r in night_rules]

                for rule in night_rules:
                    self._automation.register_rule(rule)
                    self._automation.enable_rule(rule.rule_id)
                    actions.append(f"Enabled night rule: {rule.name}")

        return actions

    def _create_night_heating_rules(
        self,
        habitat_id: str,
        config: 'HabitatDayNightConfig'
    ) -> List[AutomationRule]:
        """
        Create night-time heating rules for ceramic heater.

        Rules:
        1. Turn ON ceramic heater when cool side temp < night_temp_min
        2. Turn OFF ceramic heater when cool side temp >= night_temp_max
        """
        rules = []

        # Rule 1: Turn ON when temp drops below night minimum
        on_rule = AutomationRule(
            rule_id=f"{habitat_id}-night-heat-on",
            name=f"Night heat ON when < {config.night_temp_min}°C",
            habitat_id=habitat_id,
            sensor_id=config.cool_temp_sensor_id,
            outlet_id=config.ceramic_heater_outlet_id,
            trigger_value=config.night_temp_min,
            trigger_operator='lt',
            action_on_trigger=OutletStateEnum.ON,
            action_on_clear=None,
            hysteresis=1.0,
            min_duration_seconds=300,
            enabled=True
        )
        rules.append(on_rule)

        # Rule 2: Turn OFF when temp reaches night maximum
        off_rule = AutomationRule(
            rule_id=f"{habitat_id}-night-heat-off",
            name=f"Night heat OFF when >= {config.night_temp_max}°C",
            habitat_id=habitat_id,
            sensor_id=config.cool_temp_sensor_id,
            outlet_id=config.ceramic_heater_outlet_id,
            trigger_value=config.night_temp_max,
            trigger_operator='gte',
            action_on_trigger=OutletStateEnum.OFF,
            action_on_clear=None,
            hysteresis=1.0,
            min_duration_seconds=300,
            enabled=True
        )
        rules.append(off_rule)

        return rules

    def _get_current_time(self) -> datetime:
        """Get current time (use time provider if available)."""
        if self._time_provider:
            return self._time_provider.now()
        from datetime import timezone
        return datetime.now(timezone.utc)

    def _log_info(self, message: str, context: dict = None):
        """Log info message."""
        if self._logger:
            self._logger.info(message, context)
        else:
            print(f"[INFO] {message}")

    def _log_error(self, message: str, context: dict = None, exception: Exception = None):
        """Log error message."""
        if self._logger:
            self._logger.error(message, context, exception)
        else:
            print(f"[ERROR] {message}")
            if exception:
                print(f"  Exception: {exception}")
