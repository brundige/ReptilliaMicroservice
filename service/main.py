# main.py

"""
Main application entry point for Reptile Habitat Automation System.

This wires together all the components using mock adapters for testing.
Once this works, we'll replace mocks with real adapters one at a time.
"""

import builtins
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# =============================================================================
# Log File Setup - redirect print() to both stdout and log file
# =============================================================================
# This allows the API to stream logs to the iPad via SSE
_log_file = os.getenv("LOG_FILE")
_log_handle = None

if _log_file:
    Path(_log_file).parent.mkdir(parents=True, exist_ok=True)
    _log_handle = open(_log_file, "a", buffering=1)

_original_print = builtins.print


def _logging_print(*args, **kwargs):
    """Print wrapper that also writes to log file."""
    # Call original print for stdout
    _original_print(*args, **kwargs)
    # Also write to log file if configured
    if _log_handle:
        # Add timestamp for log file
        timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
        message = " ".join(str(arg) for arg in args)
        _log_handle.write(f"[{timestamp}] {message}\n")
        _log_handle.flush()


# Replace built-in print with our logging version
builtins.print = _logging_print

# Domain layer
from domain.models import (
    ReptileSpecies,
    SensorUnit,
    SensorMetadata,
    SensorType,
    OutletStateEnum
)
from domain.services import (
    SensorMonitoringService,
    OutletAutomationService,
    HabitatManagementService,
    DayNightService
)

# Mock adapters (no real hardware needed!)
from adapters.mock.mock_sensor import MockTemperatureHumiditySensor
from adapters.mock.mock_outlet import MockOutletController

# Real hardware adapters
from adapters.sensors.LYWSD03MMC import LYWSD03MMCSensor
from adapters.outlets.kasa import KasaOutletController, KasaConnectionError

# MongoDB adapters
from adapters.mongodb.connection import MongoDBConnection
from adapters.mongodb.repositories import (
    MongoDBSensorRepository,
    MongoDBOutletRepository,
    MongoDBHabitatRepository,
    MongoDBThresholdRepository
)

# util adapters
from adapters.utils.time_providers import (
    SystemTimeProvider,
    FixedTimeProvider,
    AstralSunTimesProvider,
    FixedSunTimesProvider
)


def create_test_app():
    """
    Create complete application with MongoDB storage.

    This uses:
    - Real Bluetooth sensors (LYWSD03MMC)
    - MongoDB for persistent storage
    - Mock outlet controller (replace with real smart outlet adapter)

    Returns:
        Dict with all services and adapters
    """
    print("=" * 60)
    print("🦎 REPTILE HABITAT AUTOMATION SYSTEM")
    print("=" * 60)
    print()

    # ═══════════════════════════════════════════════════════════
    # STEP 1: Create all the ADAPTERS (infrastructure)
    # ═══════════════════════════════════════════════════════════

    print("📦 Creating adapters...")

    # Sensor configuration from environment
    sensor_timeout = float(os.getenv("SENSOR_CONNECTION_TIMEOUT", "30.0"))
    sensor_retries = int(os.getenv("SENSOR_MAX_RETRIES", "3"))
    sensor_retry_delay = float(os.getenv("SENSOR_RETRY_DELAY", "2.0"))

    # Real BLE sensors - Xiaomi LYWSD03MMC
    warm_side_sensor = LYWSD03MMCSensor(
        device_address=os.getenv("SENSOR_WARM_SIDE_ADDRESS", "BE67157C-68B0-1E7B-141E-89E563048735"),
        sensor_id=os.getenv("SENSOR_WARM_SIDE_ID", "basking-temp-sensor"),
        location="warm_side",
        connection_timeout=sensor_timeout,
        max_retries=sensor_retries,
        retry_delay=sensor_retry_delay
    )
    print(f'  ✓ Warm side sensor created: {warm_side_sensor._sensor_id}')

    cool_side_sensor = LYWSD03MMCSensor(
        device_address=os.getenv("SENSOR_COOL_SIDE_ADDRESS", "763137C2-0D36-87EE-F64A-A21B387F16A1"),
        sensor_id=os.getenv("SENSOR_COOL_SIDE_ID", "cool-temp-sensor"),
        location="cool_side",
        connection_timeout=sensor_timeout,
        max_retries=sensor_retries,
        retry_delay=sensor_retry_delay
    )
    print(f'  ✓ Cool side sensor created: {cool_side_sensor._sensor_id}')

    # MongoDB connection and repositories
    mongo_conn = MongoDBConnection(
        uri=os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        database=os.getenv("MONGODB_DATABASE", "reptilia")
    )
    db = mongo_conn.get_database()

    sensor_repo = MongoDBSensorRepository(db)
    print("  ✓ MongoDB sensor repository created (90-day TTL)")

    threshold_repo = MongoDBThresholdRepository(db)
    print("  ✓ MongoDB threshold repository created")

    # Outlet controller - use Kasa if configured, otherwise fall back to mock
    kasa_ip = os.getenv("KASA_IP")
    if kasa_ip:
        try:
            # Parse outlet mapping from environment (JSON format)
            outlet_mapping_json = os.getenv("KASA_OUTLET_MAPPING", "{}")
            outlet_mapping = json.loads(outlet_mapping_json)

            outlet_controller = KasaOutletController(
                ip_address=kasa_ip,
                username=os.getenv("KASA_USERNAME"),
                password=os.getenv("KASA_PASSWORD"),
                outlet_mapping=outlet_mapping
            )
            print(f"  ✓ Kasa outlet controller created (device: {kasa_ip})")
            print(f"    Outlet mapping: {outlet_mapping}")
        except json.JSONDecodeError as e:
            print(f"  ⚠ Invalid KASA_OUTLET_MAPPING JSON: {e}")
            print("  ✓ Falling back to mock outlet controller")
            outlet_controller = MockOutletController()
        except KasaConnectionError as e:
            print(f"  ⚠ Kasa connection failed: {e}")
            print("  ✓ Falling back to mock outlet controller")
            outlet_controller = MockOutletController()
    else:
        outlet_controller = MockOutletController()
        print("  ✓ Mock outlet controller created (set KASA_IP to use real device)")

    outlet_repo = MongoDBOutletRepository(db)
    print("  ✓ MongoDB outlet repository created")

    habitat_repo = MongoDBHabitatRepository(db)
    print("  ✓ MongoDB habitat repository created (with species data)")

    print()

    # ═══════════════════════════════════════════════════════════
    # STEP 2: Create SERVICES (business logic)
    # ═══════════════════════════════════════════════════════════

    print("⚙️  Creating services...")

    # Create automation service (controls outlets)
    automation_service = OutletAutomationService(
        outlet_controller=outlet_controller,
        outlet_repository=outlet_repo,
        time_provider=None,  # Will use datetime.now(timezone.utc) by default
        logger=None  # Will use print() by default
    )
    print("  ✓ Outlet automation service created")

    # Create monitoring service (processes sensor readings)
    monitoring_service = SensorMonitoringService(
        sensor_repository=sensor_repo,
        threshold_repository=threshold_repo,
        automation_service=automation_service,  # Link to automation
        notification_service=None,  # Skip notifications for now
        time_provider=None,
        logger=None
    )
    print("  ✓ Sensor monitoring service created")

    # Create habitat management service (sets up habitats)
    habitat_service = HabitatManagementService(
        habitat_repository=habitat_repo,
        threshold_repository=threshold_repo,
        automation_service=automation_service,
        sensor_monitoring=monitoring_service,
        logger=None
    )
    print("  ✓ Habitat management service created")

    # Create Sun Times Provider for sunrise/sunset calculations
    # Configure location from environment variables
    latitude = float(os.getenv("HABITAT_LATITUDE", "40.7128"))  # Default: NYC
    longitude = float(os.getenv("HABITAT_LONGITUDE", "-74.0060"))
    timezone_name = os.getenv("HABITAT_TIMEZONE", "America/New_York")

    sun_times_provider = AstralSunTimesProvider(
        latitude=latitude,
        longitude=longitude,
        timezone_name=timezone_name,
        location_name="Habitat Location"
    )
    print(f"  ✓ Sun times provider created (lat: {latitude}, lon: {longitude})")

    # Create Day/Night Service - manages sunrise/sunset transitions
    day_night_service = DayNightService(
        outlet_controller=outlet_controller,
        automation_service=automation_service,
        sun_times_provider=sun_times_provider,
        time_provider=SystemTimeProvider(),
        logger=None
    )
    print("  ✓ Day/Night service created")

    # ═══════════════════════════════════════════════════════════
    # STEP 3: Set up a TEST HABITAT
    # ═══════════════════════════════════════════════════════════

    print("🦎 Setting up test habitat...")

    habitat = habitat_service.setup_habitat(
        habitat_id="test-habitat-001",
        name="Garys Leopard Gecko Enclosure",
        species=ReptileSpecies.LEOPARD_GECKO,
        sensor_config={
            'basking_temp': 'basking-temp-sensor',
            'cool_temp': 'cool-temp-sensor',
            'humidity': 'basking-humidity-sensor'
        },
        outlet_config={
            'heat_lamp': 'basking-heat-lamp',
            'ceramic_heater': 'ambient-heater',
            'humidifier': 'humidifier',
            'uvb': 'uvb-light'  # UVB outlet for sunrise/sunset control
        }
    )

    print()
    print("✅ Habitat configured successfully!")
    print(f"   Name: {habitat.name}")
    print(f"   Species: {habitat.species.value}")
    print(f"   Basking temp: {habitat.requirements.basking_temp_min}°C - {habitat.requirements.basking_temp_max}°C")
    print(f"   Cool temp: {habitat.requirements.cool_side_temp_min}°C - {habitat.requirements.cool_side_temp_max}°C")
    print(f"   Humidity: {habitat.requirements.humidity_min}% - {habitat.requirements.humidity_max}%")
    print()

    # Show automation rules that were created
    rules = automation_service.get_all_rules()
    print(f"📋 {len(rules)} automation rules created:")
    for rule in rules:
        status = "✓ enabled" if rule.enabled else "✗ disabled"
        print(f"   {status} {rule.name}")
    print()

    # ═══════════════════════════════════════════════════════════
    # STEP 4: Register habitat with Day/Night Service
    # ═══════════════════════════════════════════════════════════

    # Collect daytime heating rule IDs (these will be disabled at night)
    daytime_heat_rule_ids = [rule.rule_id for rule in rules if 'heat' in rule.name.lower()]

    day_night_service.register_habitat(
        habitat=habitat,
        daytime_heat_rule_ids=daytime_heat_rule_ids
    )

    # Show sunrise/sunset times (convert to local timezone for display)
    sunrise = day_night_service.get_sunrise()
    sunset = day_night_service.get_sunset()

    # Debug: show raw values
    print(f"   DEBUG: Raw sunrise={sunrise}, sunset={sunset}")
    print(f"   DEBUG: sunrise.tzinfo={sunrise.tzinfo}, sunset.tzinfo={sunset.tzinfo}")

    # Convert to local time for display
    try:
        from zoneinfo import ZoneInfo
        local_tz = ZoneInfo(timezone_name)
        sunrise_local = sunrise.astimezone(local_tz)
        sunset_local = sunset.astimezone(local_tz)
    except Exception as e:
        print(f"   DEBUG: Timezone conversion failed: {e}")
        sunrise_local = sunrise
        sunset_local = sunset

    print(f"☀️  Day/Night Schedule (Location: {latitude}, {longitude}):")
    print(f"   Sunrise: {sunrise_local.strftime('%H:%M %Z')} (UVB ON)")
    print(f"   Sunset:  {sunset_local.strftime('%H:%M %Z')} (UVB OFF, Heat lamp OFF)")
    print(f"   Night temp range: {habitat.requirements.night_temp_min}°C - {habitat.requirements.night_temp_max}°C")
    print()

    return {
        'warm_side_sensor': warm_side_sensor,
        'cool_side_sensor': cool_side_sensor,
        'monitoring': monitoring_service,
        'automation': automation_service,
        'habitat': habitat_service,
        'sensor_repo': sensor_repo,
        'outlet_controller': outlet_controller,
        'day_night': day_night_service,
        'habitat_obj': habitat
    }


def run_polling_loop():
    """
    Main application loop - polls sensor and processes readings.

    This simulates the actual operation:
    1. Read from sensor
    2. Process readings
    3. Automation triggers if needed
    4. Wait and repeat
    """
    # Create the app
    app = create_test_app()

    day_night = app['day_night']

    warm_side_sensor = app['warm_side_sensor']
    cool_side_sensor = app['cool_side_sensor']
    monitoring = app['monitoring']
    sensor_repo = app['sensor_repo']
    outlet_controller = app['outlet_controller']

    print("=" * 60)
    print("🔄 STARTING SENSOR POLLING LOOP")
    print("=" * 60)
    print("Press Ctrl+C to stop")
    print()

    iteration = 0

    try:
        while True:
            iteration += 1
            now = datetime.now(timezone.utc)
            print(f"[{now.strftime('%H:%M:%S')}] Iteration #{iteration}")

            # Check and update day/night mode FIRST (before sensor processing)
            # This ensures rules are enabled/disabled before automation triggers
            day_night_result = day_night.check_and_update()
            if day_night_result['mode_changed']:
                print(f"  ⚡ MODE CHANGE: Now in {day_night_result['mode'].upper()} mode")
                for action in day_night_result['actions_taken']:
                    print(f"     → {action}")

            # Read from warm side sensor
            warm_temp = None
            warm_humidity = None
            try:
                warm_temp, warm_humidity = warm_side_sensor.read_temperature_and_humidity()
                print(f"  🌡️  Warm side: {(warm_temp * 9 / 5) + 32:.1f}°F, {warm_humidity:.0f}% humidity")

                # Process warm side temperature
                monitoring.process_reading(
                    sensor_id='basking-temp-sensor',
                    value=warm_temp,
                    timestamp=now,
                    unit=SensorUnit.CELSIUS
                )
                # Process warm side humidity
                monitoring.process_reading(
                    sensor_id='basking-humidity-sensor',
                    value=warm_humidity,
                    timestamp=now,
                    unit=SensorUnit.PERCENT
                )
            except ConnectionError as e:
                print(f"  ❌ Warm side sensor failed: {e}")

            # Read from cool side sensor
            cool_temp = None
            cool_humidity = None
            try:
                cool_temp, cool_humidity = cool_side_sensor.read_temperature_and_humidity()
                print(f"  🌡️  Cool side: {(cool_temp * 9 / 5) + 32:.1f}°F, {cool_humidity:.0f}% humidity")

                # Process cool side temperature
                monitoring.process_reading(
                    sensor_id='cool-temp-sensor',
                    value=cool_temp,
                    timestamp=now,
                    unit=SensorUnit.CELSIUS
                )
                # Process cool side humidity
                monitoring.process_reading(
                    sensor_id='cool-humidity-sensor',
                    value=cool_humidity,
                    timestamp=now,
                    unit=SensorUnit.PERCENT
                )
            except ConnectionError as e:
                print(f"  ❌ Cool side sensor failed: {e}")

            # Show outlet states
            heat_lamp_state = outlet_controller.get_state('basking-heat-lamp')
            humidifier_state = outlet_controller.get_state('humidifier')

            # Try to get UVB state if available
            try:
                uvb_state = outlet_controller.get_state('uvb-light')
                uvb_indicator = "💡 ON " if uvb_state.state.value == "on" else "⚫ OFF"
            except Exception:
                uvb_indicator = "⚫ N/A"

            heat_indicator = "🔥 ON " if heat_lamp_state.state.value == "on" else "⚫ OFF"
            humid_indicator = "💨 ON " if humidifier_state.state.value == "on" else "⚫ OFF"
            mode_indicator = "☀️ DAY" if day_night_result['mode'] == 'day' else "🌙 NIGHT"

            print(f"  🔌 UVB Light: {uvb_indicator}")
            print(f"  🔌 Heat Lamp: {heat_indicator}")
            print(f"  🔌 Humidifier: {humid_indicator}")
            print(f"  ⏰ Mode: {mode_indicator}")

            # Show total readings stored
            total_readings = sensor_repo.count()
            print(f"  📊 Total readings stored: {total_readings}")

            # Calculate sleep time: minimum of polling interval and time until next sun event
            polling_interval = int(os.getenv("POLLING_INTERVAL_SECONDS", "30"))
            seconds_to_sun_event, event_type = day_night.seconds_until_next_sun_event()

            if seconds_to_sun_event < polling_interval:
                sleep_time = max(1, seconds_to_sun_event)  # At least 1 second
                print(f"  ⏰ Sleeping {sleep_time:.0f}s until {event_type}")
            else:
                sleep_time = polling_interval
                print(f"  ⏰ Sleeping {sleep_time}s (next {event_type} in {seconds_to_sun_event/60:.0f}m)")

            print()
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print()
        print("=" * 60)
        print("✋ STOPPED BY USER")
        print("=" * 60)
        print()

        # Show final statistics
        total_readings = sensor_repo.count()
        print(f"📊 Final Statistics:")
        print(f"   Total readings collected: {total_readings}")
        print(f"   Total iterations: {iteration}")
        print()

        # Show automation rule execution
        rules = app['automation'].get_all_rules()
        print(f"📋 Automation Rules:")
        for rule in rules:
            triggered = "Yes" if rule.last_triggered else "Never"
            print(f"   {rule.name}")
            print(f"      Last triggered: {triggered}")
        print()

        print("👋 Goodbye!")


def run_interactive_mode():
    """
    Interactive mode - lets you manually test features.
    """
    app = create_test_app()

    sensor = app['sensor']
    monitoring = app['monitoring']
    automation = app['automation']
    outlet_controller = app['outlet_controller']

    print("=" * 60)
    print("🎮 INTERACTIVE MODE")
    print("=" * 60)
    print()
    print("Commands:")
    print("  1 - Poll sensor once")
    print("  2 - Show habitat status")
    print("  3 - Manually turn on heat lamp")
    print("  4 - Manually turn off heat lamp")
    print("  5 - Show all automation rules")
    print("  6 - Set sensor to cold (15°C)")
    print("  7 - Set sensor to hot (45°C)")
    print("  8 - Set sensor to ideal (37°C)")
    print("  q - Quit")
    print()

    while True:
        cmd = input("Enter command: ").strip()

        if cmd == '1':
            # Poll sensor
            temp, humidity = sensor.read_temperature_and_humidity()
            now = datetime.now(timezone.utc)

            temp_reading = monitoring.process_reading(
                'basking-temp-sensor', temp, now, SensorUnit.CELSIUS
            )
            humidity_reading = monitoring.process_reading(
                'humidity-sensor', humidity, now, SensorUnit.PERCENT
            )

            print(f"✓ Polled: {temp:.1f}°C, {humidity:.1f}%")

        elif cmd == '2':
            # Show status
            status = app['habitat'].get_habitat_status('test-habitat-001')
            print("\n📊 Habitat Status:")
            print(f"   Overall: {status['overall_status']}")
            print(f"   Basking temp: {status['current_conditions']['basking_temp']}°C")
            print(f"   Humidity: {status['current_conditions']['humidity']}%")
            print()

        elif cmd == '3':
            # Manual ON
            automation.manual_control('basking-heat-lamp', OutletStateEnum.ON)
            print("✓ Heat lamp turned ON manually")

        elif cmd == '4':
            # Manual OFF
            automation.manual_control('basking-heat-lamp', OutletStateEnum.OFF)
            print("✓ Heat lamp turned OFF manually")

        elif cmd == '5':
            # Show rules
            rules = automation.get_all_rules()
            print(f"\n📋 {len(rules)} Automation Rules:")
            for rule in rules:
                status = "✓" if rule.enabled else "✗"
                triggered = f"Last: {rule.last_triggered}" if rule.last_triggered else "Never triggered"
                print(f"   {status} {rule.name} - {triggered}")
            print()

        elif cmd == '6':
            # Cold
            sensor.set_temperature(15.0)
            print("✓ Sensor set to 15°C (COLD - should trigger heating)")

        elif cmd == '7':
            # Hot
            sensor.set_temperature(45.0)
            print("✓ Sensor set to 45°C (HOT - should turn off heating)")

        elif cmd == '8':
            # Ideal
            sensor.set_temperature(37.0)
            print("✓ Sensor set to 37°C (ideal basking temp)")

        elif cmd == 'q':
            print("👋 Goodbye!")
            break

        else:
            print("❌ Unknown command")


def main():
    """Main entry point"""
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        run_interactive_mode()
    else:
        run_polling_loop()


if __name__ == '__main__':
    main()
