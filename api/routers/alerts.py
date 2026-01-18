# api/routers/alerts.py

"""
Alert endpoints for the Reptilia API.
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.database import Database

from api.database import get_db
from api.models.schemas import AlertResponse, AlertAcknowledgeRequest
from api.models.enums import AlertSeverity

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.get("", response_model=list[AlertResponse])
def list_alerts(
    sensor_id: Optional[str] = None,
    severity: Optional[AlertSeverity] = None,
    acknowledged: Optional[bool] = None,
    limit: int = Query(default=50, ge=1, le=500),
    db: Database = Depends(get_db)
):
    """Get recent alerts with optional filtering."""
    query = {}

    if sensor_id:
        query["sensor_id"] = sensor_id
    if severity:
        query["severity"] = severity.value
    if acknowledged is not None:
        query["acknowledged"] = acknowledged

    alerts = list(
        db.alerts.find(query)
        .sort("created_at", -1)
        .limit(limit)
    )

    return [_doc_to_response(a) for a in alerts]


@router.get("/{alert_id}", response_model=AlertResponse)
def get_alert(alert_id: str, db: Database = Depends(get_db)):
    """Get a specific alert."""
    alert = db.alerts.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return _doc_to_response(alert)


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
def acknowledge_alert(
    alert_id: str,
    request: AlertAcknowledgeRequest,
    db: Database = Depends(get_db)
):
    """Acknowledge an alert."""
    alert = db.alerts.find_one({"alert_id": alert_id})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    now = datetime.now(timezone.utc)

    db.alerts.update_one(
        {"alert_id": alert_id},
        {"$set": {
            "acknowledged": True,
            "acknowledged_at": now,
            "acknowledged_by": request.user
        }}
    )

    updated = db.alerts.find_one({"alert_id": alert_id})
    return _doc_to_response(updated)


@router.get("/unacknowledged/count")
def count_unacknowledged(db: Database = Depends(get_db)):
    """Get count of unacknowledged alerts by severity."""
    pipeline = [
        {"$match": {"acknowledged": False}},
        {"$group": {"_id": "$severity", "count": {"$sum": 1}}}
    ]
    results = list(db.alerts.aggregate(pipeline))

    counts = {"info": 0, "warning": 0, "critical": 0, "total": 0}
    for r in results:
        severity = r["_id"]
        count = r["count"]
        counts[severity] = count
        counts["total"] += count

    return counts


def _doc_to_response(doc: dict) -> AlertResponse:
    """Convert MongoDB document to response model."""
    return AlertResponse(
        alert_id=doc["alert_id"],
        sensor_id=doc["sensor_id"],
        severity=AlertSeverity(doc["severity"]),
        message=doc["message"],
        value=doc["value"],
        threshold_violated=doc.get("threshold_violated"),
        created_at=doc["created_at"],
        acknowledged=doc.get("acknowledged", False),
        acknowledged_at=doc.get("acknowledged_at"),
        acknowledged_by=doc.get("acknowledged_by")
    )
