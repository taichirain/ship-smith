import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from sqlalchemy.orm import Session

from .config import get_settings


logger = logging.getLogger(__name__)


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "packages", "db"))
    from shipsmith_db import Heartbeat, DeploymentLog, WebhookDelivery, NotificationDelivery, FlagAudit, ProjectAudit, DiagnosticSnapshot
    return Heartbeat, DeploymentLog, WebhookDelivery, NotificationDelivery, FlagAudit, ProjectAudit, DiagnosticSnapshot


def cleanup_heartbeats(db: Session, retention_days: int = None) -> Dict[str, Any]:
    Heartbeat, _, _, _, _, _ = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.heartbeat_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(Heartbeat).filter(Heartbeat.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} heartbeats older than {days} days")
    return {
        "table": "heartbeats",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_deployment_logs(db: Session, retention_days: int = None) -> Dict[str, Any]:
    _, DeploymentLog, _, _, _, _ = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.deployment_logs_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(DeploymentLog).filter(DeploymentLog.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} deployment logs older than {days} days")
    return {
        "table": "deployment_logs",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_webhook_deliveries(db: Session, retention_days: int = None) -> Dict[str, Any]:
    _, _, WebhookDelivery, _, _, _ = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.webhook_payload_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(WebhookDelivery).filter(WebhookDelivery.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} webhook deliveries older than {days} days")
    return {
        "table": "webhook_deliveries",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_notification_deliveries(db: Session, retention_days: int = None) -> Dict[str, Any]:
    _, _, _, NotificationDelivery, _, _ = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.notification_deliveries_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(NotificationDelivery).filter(NotificationDelivery.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} notification deliveries older than {days} days")
    return {
        "table": "notification_deliveries",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_flag_audits(db: Session, retention_days: int = None) -> Dict[str, Any]:
    _, _, _, _, FlagAudit, _ = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.flag_audits_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(FlagAudit).filter(FlagAudit.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} flag audits older than {days} days")
    return {
        "table": "flag_audits",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_project_audits(db: Session, retention_days: int = None) -> Dict[str, Any]:
    _, _, _, _, _, ProjectAudit = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.project_audits_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = db.query(ProjectAudit).filter(ProjectAudit.created_at < cutoff).delete(synchronize_session=False)
    db.commit()

    logger.info(f"Cleaned up {deleted} project audits older than {days} days")
    return {
        "table": "project_audits",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_diagnostic_snapshots(db: Session, retention_days: int = None) -> Dict[str, Any]:
    *_, DiagnosticSnapshot = _import_db_models()
    settings = get_settings()
    days = retention_days if retention_days is not None else settings.diagnostic_snapshot_retention_days
    cutoff = datetime.utcnow() - timedelta(days=days)

    deleted = (
        db.query(DiagnosticSnapshot)
        .filter(DiagnosticSnapshot.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()

    logger.info(f"Cleaned up {deleted} diagnostic snapshots older than {days} days")
    return {
        "table": "diagnostic_snapshots",
        "deleted_count": deleted,
        "retention_days": days,
        "cutoff_time": cutoff.isoformat(),
    }


def cleanup_all(db: Session) -> Dict[str, Any]:
    settings = get_settings()

    results = {
        "timestamp": datetime.utcnow().isoformat(),
        "retention_policies": {
            "heartbeats": settings.heartbeat_retention_days,
            "deployment_logs": settings.deployment_logs_retention_days,
            "webhook_deliveries": settings.webhook_payload_retention_days,
            "notification_deliveries": settings.notification_deliveries_retention_days,
            "flag_audits": settings.flag_audits_retention_days,
            "project_audits": settings.project_audits_retention_days,
            "diagnostic_snapshots": settings.diagnostic_snapshot_retention_days,
        },
        "cleanup_results": [],
        "total_deleted": 0,
    }

    cleanup_functions = [
        ("heartbeats", cleanup_heartbeats),
        ("deployment_logs", cleanup_deployment_logs),
        ("webhook_deliveries", cleanup_webhook_deliveries),
        ("notification_deliveries", cleanup_notification_deliveries),
        ("flag_audits", cleanup_flag_audits),
        ("project_audits", cleanup_project_audits),
        ("diagnostic_snapshots", cleanup_diagnostic_snapshots),
    ]

    for name, cleanup_func in cleanup_functions:
        try:
            result = cleanup_func(db)
            results["cleanup_results"].append(result)
            results["total_deleted"] += result["deleted_count"]
        except Exception as e:
            logger.error(f"Failed to cleanup {name}: {e}")
            results["cleanup_results"].append({
                "table": name,
                "error": str(e),
                "deleted_count": 0,
            })

    logger.info(f"Cleanup completed. Total deleted: {results['total_deleted']}")
    return results
