import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from .config import get_settings


logger = logging.getLogger(__name__)

DETECTED_OFFLINE_KEY = "_detected_offline_at"


def _event_details(project: Any, status: Any, threshold_seconds: int) -> Dict[str, Any]:
    return {
        "agent_id": getattr(project, "agent_id", "unknown"),
        "last_seen_at": status.agent_last_seen_at.isoformat() if status.agent_last_seen_at else None,
        "offline_threshold_minutes": max(1, threshold_seconds // 60),
    }


def _evaluate_project(
    db: Session,
    project: Any,
    status: Any,
    cutoff: datetime,
    now: datetime,
    threshold_seconds: int,
) -> str:
    if status is None:
        return "unknown"

    snapshot = dict(status.snapshot) if isinstance(status.snapshot, dict) else {}
    detected = DETECTED_OFFLINE_KEY in snapshot
    last_seen = status.agent_last_seen_at or project.created_at
    is_offline = last_seen is None or last_seen < cutoff

    if is_offline:
        status_changed = status.health_status != "offline"
        if status_changed:
            status.health_status = "offline"
        if not detected:
            snapshot[DETECTED_OFFLINE_KEY] = now.isoformat()
            status.snapshot = snapshot
        if status_changed or not detected:
            status.updated_at = now
            db.commit()

        details = _event_details(project, status, threshold_seconds)
        try:
            from .alerts import create_or_update_alert

            create_or_update_alert(db, project.id, "agent_offline", details)
        except Exception:
            logger.exception("failed to create agent offline alert for project %s", project.id)

        try:
            from .notifications import dispatch_notification

            dispatch_notification(db, project.id, "agent_offline", details)
        except Exception:
            logger.exception("failed to send agent offline notification for project %s", project.id)

        return "offline"

    if detected:
        snapshot.pop(DETECTED_OFFLINE_KEY, None)
        status.snapshot = snapshot
        status.updated_at = now
        db.commit()

        details = {"agent_id": getattr(project, "agent_id", "unknown")}
        try:
            from .alerts import resolve_alert_by_fingerprint

            resolve_alert_by_fingerprint(db, project.id, "agent_offline", details)
        except Exception:
            logger.exception("failed to resolve agent offline alert for project %s", project.id)

        try:
            from .notifications import dispatch_notification

            dispatch_notification(db, project.id, "agent_recovered", details)
        except Exception:
            logger.exception("failed to send agent recovered notification for project %s", project.id)

        return "recovered"

    return "online"


def scan_offline_projects(
    db: Session,
    threshold_seconds: Optional[int] = None,
    now: Optional[datetime] = None,
) -> Dict[str, int]:
    from shipsmith_db import Project, ProjectStatus

    settings = get_settings()
    threshold = threshold_seconds or settings.agent_offline_threshold_seconds
    current = now or datetime.utcnow()
    cutoff = current - timedelta(seconds=threshold)

    rows = (
        db.query(Project, ProjectStatus)
        .outerjoin(ProjectStatus, Project.id == ProjectStatus.project_id)
        .all()
    )

    result = {"scanned": len(rows), "offline": 0, "recovered": 0}
    for project, status in rows:
        try:
            outcome = _evaluate_project(db, project, status, cutoff, current, threshold)
        except Exception:
            logger.exception("failed to evaluate project %s", getattr(project, "id", "?"))
            continue
        if outcome == "offline":
            result["offline"] += 1
        elif outcome == "recovered":
            result["recovered"] += 1

    return result


def check_agent_offline(
    db: Session,
    project_id: int,
    threshold_seconds: Optional[int] = None,
) -> str:
    from shipsmith_db import Project, ProjectStatus

    settings = get_settings()
    threshold = threshold_seconds or settings.agent_offline_threshold_seconds
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=threshold)

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return "unknown"
    status = db.query(ProjectStatus).filter(ProjectStatus.project_id == project_id).first()
    return _evaluate_project(db, project, status, cutoff, now, threshold)


async def monitor_loop() -> None:
    from shipsmith_db import get_session

    settings = get_settings()
    interval = max(5, settings.agent_monitor_interval_seconds)

    while True:
        db = None
        try:
            db = get_session()
            result = scan_offline_projects(db)
            if result["offline"] or result["recovered"]:
                logger.info(
                    "agent monitor: scanned=%s offline=%s recovered=%s",
                    result["scanned"],
                    result["offline"],
                    result["recovered"],
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("agent monitor scan failed")
        finally:
            if db is not None:
                db.close()

        await asyncio.sleep(interval)
