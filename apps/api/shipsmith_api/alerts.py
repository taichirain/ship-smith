import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import or_


def _build_alert_fingerprint(project_id: int, alert_type: str, event_details: Dict[str, Any]) -> str:
    parts = [str(project_id), alert_type]

    if alert_type == "agent_offline":
        parts.append(event_details.get("agent_id", "unknown"))
    elif alert_type == "deployment_failed":
        parts.append(str(event_details.get("deployment_id", "")))
        if event_details.get("commit_hash"):
            parts.append(event_details["commit_hash"])
    elif alert_type == "health_unhealthy":
        parts.append(event_details.get("agent_id", "unknown"))

    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _get_alert_title(project_name: str, alert_type: str, event_details: Dict[str, Any]) -> str:
    titles = {
        "agent_offline": "Agent Offline",
        "deployment_failed": "Deploy Failed",
        "health_unhealthy": "Health Check Failed",
    }
    base = titles.get(alert_type, alert_type.replace("_", " ").title())
    return f"{base}"


def _get_alert_message(alert_type: str, event_details: Dict[str, Any]) -> Optional[str]:
    lines = []
    if alert_type == "agent_offline":
        agent_id = event_details.get("agent_id", "unknown")
        threshold = event_details.get("offline_threshold_minutes", 10)
        lines.append(f"Agent ID: {agent_id}")
        lines.append(f"Threshold: {threshold} minutes")
    elif alert_type == "deployment_failed":
        if event_details.get("error_code"):
            lines.append(f"Error: {event_details['error_code']}")
        if event_details.get("commit_hash"):
            lines.append(f"Commit: {event_details['commit_hash'][:8]}")
        if event_details.get("deployment_id"):
            lines.append(f"Deployment: #{event_details['deployment_id']}")
    elif alert_type == "health_unhealthy":
        if event_details.get("old_status"):
            lines.append(f"Previous status: {event_details['old_status']}")
        if event_details.get("new_status"):
            lines.append(f"Current status: {event_details['new_status']}")
    return "\n".join(lines) if lines else None


def _get_open_alert(
    db: Session, project_id: int, fingerprint: str):
    from shipsmith_db import Alert
    return (
        db.query(Alert)
        .filter(
            Alert.project_id == project_id,
            Alert.fingerprint == fingerprint,
            or_(Alert.status == "open", Alert.status == "acknowledged"),
        )
        .first()
    )


def create_or_update_alert(
    db: Session,
    project_id: int,
    alert_type: Literal["agent_offline", "deployment_failed", "health_unhealthy"],
    event_details: Dict[str, Any],
) -> Optional[Any]:
    from shipsmith_db import Alert, Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return None

    fingerprint = _build_alert_fingerprint(project_id, alert_type, event_details)
    now = datetime.utcnow()

    existing_alert = _get_open_alert(db, project_id, fingerprint)

    if existing_alert:
        existing_alert.last_seen_at = now
        existing_alert.updated_at = now
        existing_alert.alert_metadata = event_details
        db.commit()
        db.refresh(existing_alert)
        return existing_alert

    title = f"{_get_alert_title(project.name, alert_type, event_details)}"
    message = _get_alert_message(alert_type, event_details)

    alert = Alert(
        project_id=project_id,
        alert_type=alert_type,
        fingerprint=fingerprint,
        status="open",
        title=title,
        message=message,
        metadata=event_details,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(
    db: Session,
    alert_id: int,
    resolved_by: Optional[str] = None,
) -> Optional[Any]:
    from shipsmith_db import Alert

    alert = (
        db.query(Alert)
        .filter(Alert.id == alert_id)
        .first()
    )

    if not alert:
        return None

    now = datetime.utcnow()
    alert.status = "resolved"
    alert.resolved_by = resolved_by
    alert.resolved_at = now
    alert.updated_at = now
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert_by_fingerprint(
    db: Session,
    project_id: int,
    alert_type: str,
    event_details: Dict[str, Any],
    resolved_by: Optional[str] = None,
) -> List[Any]:
    from shipsmith_db import Alert

    fingerprint = _build_alert_fingerprint(project_id, alert_type, event_details)

    open_alerts = (
        db.query(Alert)
        .filter(
            Alert.project_id == project_id,
            Alert.fingerprint == fingerprint,
            or_(Alert.status == "open", Alert.status == "acknowledged"),
        )
        .all()
    )

    now = datetime.utcnow()
    for alert in open_alerts:
        alert.status = "resolved"
        alert.resolved_by = resolved_by
        alert.resolved_at = now
        alert.updated_at = now

    db.commit()
    return open_alerts


def acknowledge_alert(
    db: Session,
    alert_id: int,
    acknowledged_by: Optional[str] = None,
) -> Optional[Any]:
    from shipsmith_db import Alert

    alert = (
        db.query(Alert)
        .filter(Alert.id == alert_id)
        .first()
    )

    if not alert:
        return None

    if alert.status != "open":
        return alert

    now = datetime.utcnow()
    alert.status = "acknowledged"
    alert.acknowledged_by = acknowledged_by
    alert.acknowledged_at = now
    alert.updated_at = now
    db.commit()
    db.refresh(alert)
    return alert


def list_alerts(
    db: Session,
    project_id: Optional[int] = None,
    status: Optional[List[str]] = None,
    alert_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[List[Any], dict]:
    from shipsmith_db import Alert, Project

    query = db.query(Alert)

    if project_id is not None:
        query = query.filter(Alert.project_id == project_id)

    if status:
        query = query.filter(Alert.status.in_(status))

    if alert_type:
        query = query.filter(Alert.alert_type == alert_type)

    total = query.count()

    open_count = query.filter(Alert.status == "open").count()
    acknowledged_count = query.filter(Alert.status == "acknowledged").count()
    resolved_count = query.filter(Alert.status == "resolved").count()

    query = query.order_by(Alert.created_at.desc())
    alerts = query.offset(offset).limit(limit).all()

    counts = {
        "total": total,
        "open_count": open_count,
        "acknowledged_count": acknowledged_count,
        "resolved_count": resolved_count,
    }

    return alerts, counts
