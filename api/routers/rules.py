# api/routers/rules.py

"""
Automation rules endpoints for the Reptilia API.
"""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import (
    AutomationRuleResponse,
    AutomationRuleCreate,
    AutomationRuleUpdate
)
from api.models.enums import OutletState, TriggerOperator

router = APIRouter(prefix="/rules", tags=["Automation Rules"])


@router.get("", response_model=list[AutomationRuleResponse])
def list_rules(db: Database = Depends(get_db)):
    """List all registered automation rules."""
    rules = list(db.automation_rules.find({}))
    return [_doc_to_response(r) for r in rules]


@router.get("/{rule_id}", response_model=AutomationRuleResponse)
def get_rule(rule_id: str, db: Database = Depends(get_db)):
    """Get a specific automation rule."""
    rule = db.automation_rules.find_one({"rule_id": rule_id})
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return _doc_to_response(rule)


@router.post("", response_model=AutomationRuleResponse, status_code=201)
def create_rule(rule: AutomationRuleCreate, db: Database = Depends(get_db)):
    """Create a custom automation rule."""
    existing = db.automation_rules.find_one({"rule_id": rule.rule_id})
    if existing:
        raise HTTPException(status_code=409, detail="Rule already exists")

    doc = {
        "rule_id": rule.rule_id,
        "name": rule.name,
        "habitat_id": rule.habitat_id,
        "sensor_id": rule.sensor_id,
        "outlet_id": rule.outlet_id,
        "trigger_value": rule.trigger_value,
        "trigger_operator": rule.trigger_operator.value,
        "action_on_trigger": rule.action_on_trigger.value,
        "action_on_clear": rule.action_on_clear.value if rule.action_on_clear else None,
        "min_duration_seconds": rule.min_duration_seconds,
        "hysteresis": rule.hysteresis,
        "enabled": True,
        "last_triggered": None
    }

    db.automation_rules.insert_one(doc)
    return _doc_to_response(doc)


@router.put("/{rule_id}", response_model=AutomationRuleResponse)
def update_rule(
    rule_id: str,
    update: AutomationRuleUpdate,
    db: Database = Depends(get_db)
):
    """Update an automation rule."""
    existing = db.automation_rules.find_one({"rule_id": rule_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Rule not found")

    # Build update document with only provided fields
    update_doc = {}
    if update.name is not None:
        update_doc["name"] = update.name
    if update.trigger_value is not None:
        update_doc["trigger_value"] = update.trigger_value
    if update.trigger_operator is not None:
        update_doc["trigger_operator"] = update.trigger_operator.value
    if update.action_on_trigger is not None:
        update_doc["action_on_trigger"] = update.action_on_trigger.value
    if update.action_on_clear is not None:
        update_doc["action_on_clear"] = update.action_on_clear.value
    if update.min_duration_seconds is not None:
        update_doc["min_duration_seconds"] = update.min_duration_seconds
    if update.hysteresis is not None:
        update_doc["hysteresis"] = update.hysteresis
    if update.enabled is not None:
        update_doc["enabled"] = update.enabled

    if update_doc:
        db.automation_rules.update_one({"rule_id": rule_id}, {"$set": update_doc})

    updated = db.automation_rules.find_one({"rule_id": rule_id})
    return _doc_to_response(updated)


@router.delete("/{rule_id}", status_code=204)
def delete_rule(rule_id: str, db: Database = Depends(get_db)):
    """Delete an automation rule."""
    result = db.automation_rules.delete_one({"rule_id": rule_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")


@router.post("/{rule_id}/enable", response_model=AutomationRuleResponse)
def enable_rule(rule_id: str, db: Database = Depends(get_db)):
    """Enable a disabled rule."""
    result = db.automation_rules.update_one(
        {"rule_id": rule_id},
        {"$set": {"enabled": True}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule = db.automation_rules.find_one({"rule_id": rule_id})
    return _doc_to_response(rule)


@router.post("/{rule_id}/disable", response_model=AutomationRuleResponse)
def disable_rule(rule_id: str, db: Database = Depends(get_db)):
    """Temporarily disable a rule."""
    result = db.automation_rules.update_one(
        {"rule_id": rule_id},
        {"$set": {"enabled": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule = db.automation_rules.find_one({"rule_id": rule_id})
    return _doc_to_response(rule)


def _doc_to_response(doc: dict) -> AutomationRuleResponse:
    """Convert MongoDB document to response model."""
    return AutomationRuleResponse(
        rule_id=doc["rule_id"],
        name=doc["name"],
        habitat_id=doc["habitat_id"],
        sensor_id=doc["sensor_id"],
        outlet_id=doc["outlet_id"],
        trigger_value=doc["trigger_value"],
        trigger_operator=TriggerOperator(doc["trigger_operator"]),
        action_on_trigger=OutletState(doc["action_on_trigger"]),
        action_on_clear=OutletState(doc["action_on_clear"]) if doc.get("action_on_clear") else None,
        min_duration_seconds=doc.get("min_duration_seconds", 300),
        hysteresis=doc.get("hysteresis", 2.0),
        enabled=doc.get("enabled", True),
        last_triggered=doc.get("last_triggered")
    )
