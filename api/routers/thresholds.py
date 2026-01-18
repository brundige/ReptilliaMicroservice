# api/routers/thresholds.py

"""
Threshold configuration endpoints for the Reptilia API.
"""

from fastapi import APIRouter, Depends, HTTPException
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import ThresholdResponse, ThresholdUpdate

router = APIRouter(prefix="/thresholds", tags=["Thresholds"])


@router.get("/{sensor_id}", response_model=ThresholdResponse)
def get_threshold(sensor_id: str, db: Database = Depends(get_db)):
    """Get threshold configuration for a sensor."""
    threshold = db.thresholds.find_one({"sensor_id": sensor_id})
    if not threshold:
        raise HTTPException(status_code=404, detail="Threshold not found")
    return _doc_to_response(threshold)


@router.put("/{sensor_id}", response_model=ThresholdResponse)
def update_threshold(
    sensor_id: str,
    update: ThresholdUpdate,
    db: Database = Depends(get_db)
):
    """Update threshold configuration (override species defaults)."""
    existing = db.thresholds.find_one({"sensor_id": sensor_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Threshold not found")

    # Build update document with only provided fields
    update_doc = {}
    if update.min_value is not None:
        update_doc["min_value"] = update.min_value
    if update.max_value is not None:
        update_doc["max_value"] = update.max_value
    if update.warning_min is not None:
        update_doc["warning_min"] = update.warning_min
    if update.warning_max is not None:
        update_doc["warning_max"] = update.warning_max
    if update.hysteresis is not None:
        update_doc["hysteresis"] = update.hysteresis

    if update_doc:
        db.thresholds.update_one({"sensor_id": sensor_id}, {"$set": update_doc})

    # Return updated document
    updated = db.thresholds.find_one({"sensor_id": sensor_id})
    return _doc_to_response(updated)


@router.get("/habitat/{habitat_id}", response_model=list[ThresholdResponse])
def get_habitat_thresholds(habitat_id: str, db: Database = Depends(get_db)):
    """Get all thresholds for a habitat."""
    # Get habitat to find sensor IDs
    habitat = db.habitats.find_one({"habitat_id": habitat_id})
    if not habitat:
        raise HTTPException(status_code=404, detail="Habitat not found")

    sensor_ids = [
        habitat["basking_temp_sensor_id"],
        habitat["cool_temp_sensor_id"],
        habitat["humidity_sensor_id"]
    ]

    thresholds = list(db.thresholds.find({"sensor_id": {"$in": sensor_ids}}))
    return [_doc_to_response(t) for t in thresholds]


def _doc_to_response(doc: dict) -> ThresholdResponse:
    """Convert MongoDB document to response model."""
    return ThresholdResponse(
        sensor_id=doc["sensor_id"],
        zone_type=doc["zone_type"],
        min_value=doc["min_value"],
        max_value=doc["max_value"],
        warning_min=doc.get("warning_min"),
        warning_max=doc.get("warning_max"),
        hysteresis=doc.get("hysteresis", 2.0)
    )
