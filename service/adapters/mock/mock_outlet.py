# adapters/mock/mock_outlet.py

"""
Mock outlet controller - simulates smart outlets without real hardware.
"""

from typing import Dict
from datetime import datetime, timezone

from domain.ports import OutletController
from domain.models import OutletState, OutletStateEnum, ControlMode


class MockOutletController(OutletController):
    """
    Fake outlet controller - just prints and tracks state.
    No real hardware needed!
    """

    def __init__(self):
        self._states: Dict[str, OutletState] = {}
        print("🔌 MockOutletController created")

    def turn_on(self, outlet_id: str) -> bool:
        """Simulate turning on outlet"""
        print(f"🔌 ✅ Turning ON outlet: {outlet_id}")

        self._states[outlet_id] = OutletState(
            outlet_id=outlet_id,
            state=OutletStateEnum.ON,
            last_changed=datetime.now(timezone.utc),
            mode=ControlMode.AUTOMATIC
        )
        return True

    def turn_off(self, outlet_id: str) -> bool:
        """Simulate turning off outlet"""
        print(f"🔌 ⚫ Turning OFF outlet: {outlet_id}")

        self._states[outlet_id] = OutletState(
            outlet_id=outlet_id,
            state=OutletStateEnum.OFF,
            last_changed=datetime.now(timezone.utc),
            mode=ControlMode.AUTOMATIC
        )
        return True

    def get_state(self, outlet_id: str) -> OutletState:
        """Get current outlet state"""
        if outlet_id not in self._states:
            # Default to OFF for unknown outlets
            return OutletState(
                outlet_id=outlet_id,
                state=OutletStateEnum.UNKNOWN,
                last_changed=datetime.now(timezone.utc),
                mode=ControlMode.AUTOMATIC
            )
        return self._states[outlet_id]

    def toggle(self, outlet_id: str) -> OutletState:
        """Toggle outlet state"""
        current = self.get_state(outlet_id)

        if current.state == OutletStateEnum.ON:
            self.turn_off(outlet_id)
        else:
            self.turn_on(outlet_id)

        return self.get_state(outlet_id)

    # ===== Testing helpers =====

    def reset_all(self):
        """Turn off all outlets"""
        for outlet_id in list(self._states.keys()):
            self.turn_off(outlet_id)

    def get_all_states(self) -> Dict[str, OutletState]:
        """Get all outlet states (for testing/debugging)"""
        return self._states.copy()