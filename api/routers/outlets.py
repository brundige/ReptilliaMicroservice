# api/routers/outlets.py

"""
Outlet control endpoints for the Reptilia API.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4
from fastapi import APIRouter, Depends,  Query
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    OutletStatusResponse,
    OutletControlRequest,
    OutletCommandResponse,
    OutletHistoryResponse,
    RuleInfo
)
from api.models.enums import OutletState, ControlMode

router = APIRouter(prefix="/outlets", tags=["Outlets"])


@router.get("/{outlet_id}/status", response_model=OutletStatusResponse)
def get_outlet_status(outlet_id: str, db: Database = Depends(get_db)):
    """Get current status of an outlet."""
    state = db.outlet_states.find_one({"outlet_id": outlet_id})

    # Get rules associated with this outlet
    rules = list(db.automation_rules.find({"outlet_id": outlet_id}))
    rule_infos = [
        RuleInfo(
            rule_id=r["rule_id"],
            name=r["name"],
            sensor=r["sensor_id"],
            enabled=r.get("enabled", True),
            trigger=f"{r['trigger_operator']} {r['trigger_value']}"
        )
        for r in rules
    ]

    if not state:
        return OutletStatusResponse(
            outlet_id=outlet_id,
            state=OutletState.UNKNOWN,
            rules=rule_infos
        )

    return OutletStatusResponse(
        outlet_id=outlet_id,
        state=OutletState(state["state"]),
        last_changed=state.get("last_changed"),
        mode=ControlMode(state.get("mode", "automatic")),
        power_watts=state.get("power_watts"),
        rules=rule_infos
    )


@router.post("/{outlet_id}/control", response_model=OutletCommandResponse)
def control_outlet(
    outlet_id: str,
    request: OutletControlRequest,
    db: Database = Depends(get_db)
):
    """Manually control an outlet (override automation)."""
    now = datetime.now(timezone.utc)
    command_id = str(uuid4())

    # Create command record
    command = {
        "command_id": command_id,
        "outlet_id": outlet_id,
        "desired_state": request.state.value,
        "reason": "Manual control",
        "triggered_by_sensor": None,
        "triggered_by_user": request.user,
        "timestamp": now,
        "executed": True,  # Assume immediate execution
        "execution_result": "success"
    }
    db.outlet_commands.insert_one(command)

    # Update outlet state
    db.outlet_states.update_one(
        {"outlet_id": outlet_id},
        {"$set": {
            "outlet_id": outlet_id,
            "state": request.state.value,
            "last_changed": now,
            "mode": ControlMode.MANUAL.value
        }},
        upsert=True
    )

    return OutletCommandResponse(
        command_id=command_id,
        desired_state=request.state,
        reason="Manual control",
        triggered_by_user=request.user,
        timestamp=now,
        executed=True,
        execution_result="success"
    )


@router.get("/{outlet_id}/history", response_model=OutletHistoryResponse)
def get_outlet_history(
    outlet_id: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    hours: int = Query(default=24, ge=1, le=720),
    db: Database = Depends(get_db)
):
    """Get command history for an outlet."""
    # Use explicit times if provided, otherwise use hours
    if start_time and end_time:
        query_start = start_time
        query_end = end_time
    else:
        query_end = datetime.now(timezone.utc)
        query_start = query_end - timedelta(hours=hours)

    commands = list(db.outlet_commands.find({
        "outlet_id": outlet_id,
        "timestamp": {"$gte": query_start, "$lte": query_end}
    }).sort("timestamp", -1))

    return OutletHistoryResponse(
        outlet_id=outlet_id,
        commands=[
            OutletCommandResponse(
                command_id=c["command_id"],
                desired_state=OutletState(c["desired_state"]),
                reason=c["reason"],
                triggered_by_sensor=c.get("triggered_by_sensor"),
                triggered_by_user=c.get("triggered_by_user"),
                timestamp=c["timestamp"],
                executed=c.get("executed", False),
                execution_result=c.get("execution_result")
            )
            for c in commands
        ]
    )
