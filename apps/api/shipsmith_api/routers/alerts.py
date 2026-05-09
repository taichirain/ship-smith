from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..schemas import AlertResponse, AlertListResponse, AlertStatus, AlertType
from ..alerts import list_alerts, acknowledge_alert, resolve_alert


router = APIRouter(prefix="/alerts", tags=["alerts"])


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Alert, Project
    return Alert, Project


def _to_response(db_session: Session, alert) -> AlertResponse:
    Alert, Project = _import_db_models()
    project_name = None
    if alert.project:
        project_name = alert.project.name
    else:
        project = db_session.query(Project).filter(Project.id == alert.project_id).first()
        if project:
            project_name = project.name

    return AlertResponse(
        id=alert.id,
        project_id=alert.project_id,
        alert_type=alert.alert_type,
        fingerprint=alert.fingerprint,
        status=alert.status,
        title=alert.title,
        message=alert.message,
        metadata=alert.alert_metadata,
        acknowledged_by=alert.acknowledged_by,
        acknowledged_at=alert.acknowledged_at,
        resolved_by=alert.resolved_by,
        resolved_at=alert.resolved_at,
        first_seen_at=alert.first_seen_at,
        last_seen_at=alert.last_seen_at,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        project_name=project_name,
    )


@router.get("", response_model=AlertListResponse)
async def list_alerts_endpoint(
    project_id: Optional[int] = Query(default=None),
    status: Optional[List[AlertStatus]] = Query(default=None),
    alert_type: Optional[AlertType] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    alerts, counts = list_alerts(
        db=db,
        project_id=project_id,
        status=status,
        alert_type=alert_type,
        limit=limit,
        offset=offset,
    )

    alert_responses = [_to_response(db, a) for a in alerts]

    return AlertListResponse(
        alerts=alert_responses,
        total=counts["total"],
        open_count=counts["open_count"],
        acknowledged_count=counts["acknowledged_count"],
        resolved_count=counts["resolved_count"],
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertResponse)
async def acknowledge_alert_endpoint(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    username = current_user.get("sub")

    alert = acknowledge_alert(
        db=db,
        alert_id=alert_id,
        acknowledged_by=username,
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    return _to_response(db, alert)


@router.post("/{alert_id}/resolve", response_model=AlertResponse)
async def resolve_alert_endpoint(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    username = current_user.get("sub")

    alert = resolve_alert(
        db=db,
        alert_id=alert_id,
        resolved_by=username,
    )

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with id {alert_id} not found",
        )

    return _to_response(db, alert)
