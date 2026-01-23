# adapters/outlets/kasa.py

"""
Kasa smart plug/powerstrip adapter implementing the OutletController port.

This adapter communicates with TP-Link Kasa smart devices to control
power outlets for habitat heating, lighting, and humidity equipment.
"""

import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime, timezone

from domain.ports import OutletController
from domain.models import OutletState, OutletStateEnum, ControlMode

logger = logging.getLogger(__name__)

# Import kasa with graceful fallback
try:
    from kasa import Discover
    from kasa.exceptions import TimeoutError as KasaTimeoutError
    KASA_AVAILABLE = True
except ImportError:
    KASA_AVAILABLE = False
    logger.warning("kasa module not available - Kasa outlet functionality disabled")


class KasaConnectionError(Exception):
    """Raised when unable to connect to Kasa device."""
    pass


class KasaOutletController(OutletController):
    """
    Adapter for TP-Link Kasa smart plugs and powerstrips.

    Implements the OutletController port to control power outlets.
    Supports both single plugs and multi-outlet powerstrips.

    Configuration:
        - ip_address: IP address of the Kasa device
        - username: Kasa cloud account username (for newer devices)
        - password: Kasa cloud account password (for newer devices)
        - outlet_mapping: Dict mapping outlet_id strings to device indices
    """

    def __init__(
        self,
        ip_address: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        outlet_mapping: Optional[Dict[str, int]] = None,
        connection_timeout: float = 10.0
    ):
        """
        Initialize the Kasa outlet controller.

        Args:
            ip_address: IP address of the Kasa device
            username: Optional Kasa account username for authentication
            password: Optional Kasa account password for authentication
            outlet_mapping: Optional dict mapping outlet_id to device index (1-based).
                           If not provided, outlet_id is parsed as integer index.
            connection_timeout: Connection timeout in seconds
        """
        if not KASA_AVAILABLE:
            raise KasaConnectionError("kasa module not installed")

        self._ip_address = ip_address
        self._username = username
        self._password = password
        self._outlet_mapping = outlet_mapping or {}
        self._connection_timeout = connection_timeout
        self._device_cache = None
        self._last_error: Optional[str] = None

        logger.info(f"KasaOutletController initialized for device at {ip_address}")

    def _get_outlet_index(self, outlet_id: str) -> int:
        """
        Convert outlet_id to device index (0-based).

        Args:
            outlet_id: String identifier for the outlet

        Returns:
            0-based index for the outlet

        Raises:
            ValueError: If outlet_id cannot be resolved to an index
        """
        # Check mapping first
        if outlet_id in self._outlet_mapping:
            return self._outlet_mapping[outlet_id] - 1  # Convert to 0-based

        # Try parsing as integer (1-based input)
        try:
            index = int(outlet_id)
            return index - 1  # Convert to 0-based
        except ValueError:
            raise ValueError(
                f"Unknown outlet_id '{outlet_id}'. "
                f"Provide a numeric index or configure outlet_mapping."
            )

    async def _get_device(self):
        """
        Discover and return the Kasa device.

        Returns:
            Kasa device instance

        Raises:
            KasaConnectionError: If device cannot be reached
        """
        try:
            device = await Discover.discover_single(
                self._ip_address,
                username=self._username,
                password=self._password,
                timeout=self._connection_timeout
            )
            return device
        except KasaTimeoutError as e:
            logger.warning(f"Kasa device at {self._ip_address} timed out")
            raise KasaConnectionError(f"Device timeout: {self._ip_address}") from e
        except Exception as e:
            logger.error(f"Failed to connect to Kasa device: {e}")
            raise KasaConnectionError(f"Connection failed: {e}") from e

    async def _safe_update(self, obj) -> None:
        """Safely call update() on a device or module."""
        if obj is None:
            return
        update_fn = getattr(obj, "update", None)
        if callable(update_fn):
            try:
                result = update_fn()
                if asyncio.iscoroutine(result):
                    await result
            except Exception:
                logger.debug("_safe_update failed", exc_info=True)

    async def _safe_close(self, dev) -> None:
        """Safely close device connection and underlying aiohttp session."""
        if dev is None:
            return

        # Try disconnect method first (python-kasa >= 0.5)
        disconnect_fn = getattr(dev, "disconnect", None)
        if callable(disconnect_fn):
            try:
                result = disconnect_fn()
                if asyncio.iscoroutine(result):
                    await result
                return
            except Exception:
                logger.debug("disconnect failed", exc_info=True)

        # Try closing the protocol directly (handles aiohttp session)
        protocol = getattr(dev, "protocol", None)
        if protocol:
            close_fn = getattr(protocol, "close", None)
            if callable(close_fn):
                try:
                    result = close_fn()
                    if asyncio.iscoroutine(result):
                        await result
                    return
                except Exception:
                    logger.debug("protocol.close failed", exc_info=True)

        # Fall back to legacy methods
        for method_name in ("async_close", "close"):
            fn = getattr(dev, method_name, None)
            if callable(fn):
                try:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
                    return
                except Exception:
                    logger.debug(f"{method_name} failed", exc_info=True)

    def _get_relay(self, dev, index: int):
        """
        Get the relay/child device at the given index.

        Args:
            dev: Kasa device
            index: 0-based outlet index

        Returns:
            Relay/child object or None
        """
        relays = getattr(dev, "relays", None) or getattr(dev, "children", None)
        if relays and 0 <= index < len(relays):
            return relays[index]
        return None

    async def _get_outlet_state_async(self, outlet_id: str) -> OutletState:
        """Async implementation of get_state."""
        dev = None
        try:
            index = self._get_outlet_index(outlet_id)
            dev = await self._get_device()
            await self._safe_update(dev)

            relay = self._get_relay(dev, index)
            if relay:
                await self._safe_update(relay)
                is_on = getattr(relay, "is_on", None)
            else:
                # Single plug device
                is_on = getattr(dev, "is_on", None)

            if is_on is None:
                state = OutletStateEnum.UNKNOWN
            else:
                state = OutletStateEnum.ON if is_on else OutletStateEnum.OFF

            self._last_error = None
            return OutletState(
                outlet_id=outlet_id,
                state=state,
                last_changed=datetime.now(timezone.utc),
                mode=ControlMode.AUTOMATIC
            )

        except (KasaConnectionError, ValueError) as e:
            self._last_error = str(e)
            logger.error(f"Failed to get state for outlet {outlet_id}: {e}")
            return OutletState(
                outlet_id=outlet_id,
                state=OutletStateEnum.ERROR,
                last_changed=datetime.now(timezone.utc),
                mode=ControlMode.AUTOMATIC
            )
        finally:
            await self._safe_close(dev)

    async def _set_outlet_state_async(self, outlet_id: str, turn_on: bool) -> bool:
        """
        Async implementation of turn_on/turn_off.

        Args:
            outlet_id: Outlet identifier
            turn_on: True to turn on, False to turn off

        Returns:
            True if successful, False otherwise
        """
        dev = None
        action = "on" if turn_on else "off"

        try:
            index = self._get_outlet_index(outlet_id)
            dev = await self._get_device()
            await self._safe_update(dev)

            relay = self._get_relay(dev, index)

            if relay:
                await self._safe_update(relay)
                method_name = "turn_on" if turn_on else "turn_off"
                fn = getattr(relay, method_name, None)

                if fn is None:
                    # Try device-level API with index
                    dev_fn = getattr(dev, method_name, None)
                    if dev_fn:
                        result = dev_fn(index)
                        if asyncio.iscoroutine(result):
                            await result
                    else:
                        raise RuntimeError(f"No method to turn {action} outlet")
                else:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
            else:
                # Single plug device
                method_name = "turn_on" if turn_on else "turn_off"
                fn = getattr(dev, method_name, None)
                if fn:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
                else:
                    raise RuntimeError(f"No method to turn {action} outlet")

            self._last_error = None
            logger.info(f"Successfully turned {action} outlet {outlet_id}")
            return True

        except (KasaConnectionError, ValueError, RuntimeError) as e:
            self._last_error = str(e)
            logger.error(f"Failed to turn {action} outlet {outlet_id}: {e}")
            return False
        finally:
            await self._safe_close(dev)

    def turn_on(self, outlet_id: str) -> bool:
        """
        Turn on an outlet.

        Args:
            outlet_id: Which outlet to turn on (index or mapped name)

        Returns:
            True if successful, False otherwise
        """
        return asyncio.run(self._set_outlet_state_async(outlet_id, turn_on=True))

    def turn_off(self, outlet_id: str) -> bool:
        """
        Turn off an outlet.

        Args:
            outlet_id: Which outlet to turn off (index or mapped name)

        Returns:
            True if successful, False otherwise
        """
        return asyncio.run(self._set_outlet_state_async(outlet_id, turn_on=False))

    def get_state(self, outlet_id: str) -> OutletState:
        """
        Get current state of an outlet.

        Args:
            outlet_id: Which outlet to check (index or mapped name)

        Returns:
            OutletState with current state
        """
        return asyncio.run(self._get_outlet_state_async(outlet_id))

    def toggle(self, outlet_id: str) -> OutletState:
        """
        Toggle outlet state.

        Args:
            outlet_id: Which outlet to toggle (index or mapped name)

        Returns:
            OutletState with new state after toggle
        """
        current_state = self.get_state(outlet_id)

        if current_state.state == OutletStateEnum.ON:
            self.turn_off(outlet_id)
        else:
            self.turn_on(outlet_id)

        return self.get_state(outlet_id)

    @property
    def ip_address(self) -> str:
        """Get the device IP address."""
        return self._ip_address

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message, if any."""
        return self._last_error

    @property
    def is_available(self) -> bool:
        """Check if Kasa library is available."""
        return KASA_AVAILABLE

    @classmethod
    def from_config(
        cls,
        config: 'PowerStripConfig',
        connection_timeout: float = 10.0
    ) -> 'KasaOutletController':
        """
        Factory method to create controller from PowerStripConfig.

        Args:
            config: PowerStripConfig object from habitat configuration
            connection_timeout: Connection timeout in seconds

        Returns:
            Configured KasaOutletController instance
        """
        # Import here to avoid circular imports
        from domain.models import PowerStripConfig

        # Build outlet mapping from config
        outlet_mapping = {}
        for outlet in config.outlets:
            outlet_mapping[outlet.outlet_id] = outlet.plug_number

        return cls(
            ip_address=config.ip,
            username=config.username,
            password=config.password,
            outlet_mapping=outlet_mapping,
            connection_timeout=connection_timeout
        )