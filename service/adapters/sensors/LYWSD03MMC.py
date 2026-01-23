# adapters/sensors/LYWSD03MMC.py

"""
Bluetooth Low Energy adapter for Xiaomi LYWSD03MMC temperature/humidity sensor.

This is a driven adapter (secondary adapter) that implements the SensorHardwareInterface port.
It handles all BLE communication details, hiding them from the domain.
"""

import asyncio
from typing import Optional
from bleak import BleakClient
from bleak.exc import BleakError

from domain.ports import SensorHardwareInterface
from domain.models import SensorMetadata, SensorType, SensorUnit


# LYWSD03MMC BLE characteristic UUID for temperature/humidity data
_TEMP_HUMIDITY_CHAR_UUID = "ebe0ccc1-7a0a-4b0c-8a1a-6ff2997da3a6"


class LYWSD03MMCSensor(SensorHardwareInterface):
    """
    Adapter for Xiaomi LYWSD03MMC Bluetooth temperature/humidity sensor.

    This sensor uses BLE to transmit temperature and humidity readings.
    Connection is made on-demand to preserve battery life.
    """

    def __init__(
        self,
        device_address: str,
        sensor_id: str,
        location: str,
        connection_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ):
        """
        Initialize the LYWSD03MMC sensor adapter.

        Args:
            device_address: BLE MAC address or UUID of the sensor
            sensor_id: Unique identifier for this sensor in the system
            location: Human-readable location (e.g., "warm_side", "cool_side")
            connection_timeout: Timeout for BLE connection in seconds
            max_retries: Number of connection attempts before giving up
            retry_delay: Seconds to wait between retry attempts
        """
        self._device_address = device_address
        self._sensor_id = sensor_id
        self._location = location
        self._connection_timeout = connection_timeout
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._last_error: Optional[str] = None

    def read_temperature_and_humidity(self) -> tuple[float, float]:
        """
        Read temperature and humidity from the sensor with retry logic.

        Establishes a BLE connection, reads the characteristic, then disconnects
        to preserve battery life. Retries on failure.

        Returns:
            Tuple of (temperature_celsius, humidity_percent)

        Raises:
            ConnectionError: If unable to connect after all retries
            ValueError: If sensor returns invalid data
        """
        last_exception = None

        for attempt in range(1, self._max_retries + 1):
            try:
                print(f"    [{self._sensor_id}] Connection attempt {attempt}/{self._max_retries}...")
                temp_c, humidity = asyncio.run(self._read_sensor_async())
                self._last_error = None
                return temp_c, humidity
            except BleakError as e:
                last_exception = e
                self._last_error = str(e)
                if attempt < self._max_retries:
                    print(f"    [{self._sensor_id}] Attempt {attempt} failed, retrying in {self._retry_delay}s...")
                    asyncio.run(asyncio.sleep(self._retry_delay))
            except Exception as e:
                self._last_error = str(e)
                raise

        raise ConnectionError(
            f"Failed to connect to sensor {self._sensor_id} after {self._max_retries} attempts: {last_exception}"
        )

    async def _read_sensor_async(self) -> tuple[float, float]:
        """
        Internal async method to perform the BLE read.

        Returns:
            Tuple of (temperature_celsius, humidity_percent)
        """
        client = BleakClient(
            self._device_address,
            timeout=self._connection_timeout
        )
        try:
            await client.connect()
            data = await client.read_gatt_char(_TEMP_HUMIDITY_CHAR_UUID)
            return self._parse_sensor_data(data)
        finally:
            # Disconnect errors are non-fatal - we already have the data
            try:
                await client.disconnect()
            except Exception:
                pass  # Ignore D-Bus/disconnect errors

    @staticmethod
    def _parse_sensor_data(data: bytearray) -> tuple[float, float]:
        """
        Parse raw BLE data into temperature and humidity values.

        The LYWSD03MMC sends:
        - Bytes 0-1: Temperature in 0.01°C units (little-endian, signed)
        - Byte 2: Humidity percentage

        Args:
            data: Raw bytearray from BLE characteristic

        Returns:
            Tuple of (temperature_celsius, humidity_percent)

        Raises:
            ValueError: If data format is invalid
        """
        if len(data) < 3:
            raise ValueError(f"Invalid data length: expected >= 3, got {len(data)}")

        temp_c = int.from_bytes(data[0:2], byteorder='little', signed=True) / 100.0
        humidity = float(data[2])

        return temp_c, humidity

    def is_healthy(self) -> bool:
        """
        Check if the sensor is responding correctly.

        Attempts a connection and read to verify sensor availability.

        Returns:
            True if sensor responds successfully, False otherwise
        """
        try:
            self.read_temperature_and_humidity()
            return True
        except Exception:
            return False

    def get_metadata(self) -> SensorMetadata:
        """
        Get sensor metadata information.

        Returns:
            SensorMetadata with sensor details
        """
        return SensorMetadata(
            sensor_id=self._sensor_id,
            sensor_type=SensorType.TEMPERATURE,  # Primary type; also reads humidity
            unit=SensorUnit.CELSIUS,
            location=self._location,
            manufacturer="Xiaomi",
            model="LYWSD03MMC",
            min_value=-9.9,   # Sensor spec: -9.9°C to 60°C
            max_value=60.0,
            accuracy=0.1
        )

    @property
    def device_address(self) -> str:
        """Get the BLE device address."""
        return self._device_address

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message, if any."""
        return self._last_error

    @classmethod
    def from_config(
        cls,
        config: 'SensorConfig',
        connection_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 2.0
    ) -> 'LYWSD03MMCSensor':
        """
        Factory method to create sensor from SensorConfig.

        Args:
            config: SensorConfig object from habitat configuration
            connection_timeout: Timeout for BLE connection in seconds
            max_retries: Number of connection attempts before giving up
            retry_delay: Seconds to wait between retry attempts

        Returns:
            Configured LYWSD03MMCSensor instance
        """
        # Import here to avoid circular imports
        from domain.models import SensorConfig
        return cls(
            device_address=config.ble_address,
            sensor_id=config.sensor_id,
            location=config.location.value,
            connection_timeout=connection_timeout,
            max_retries=max_retries,
            retry_delay=retry_delay
        )