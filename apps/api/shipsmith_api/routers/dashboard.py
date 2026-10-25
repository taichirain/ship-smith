from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..agent_health import is_agent_offline
from ..schemas import (
    DashboardSummaryResponse,
    DashboardSummary,
    AnomalyProject,
    ChangeEvent,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])

def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import (
        Project,
        ProjectStatus,
        Deployment,
        FlagAudit,
        WebhookDelivery,
    )
    return Project, ProjectStatus, Deployment, FlagAudit, WebhookDelivery


def _is_offline(agent_last_seen_at: datetime) -> bool:
    return is_agent_offline(agent_last_seen_at)


def _get_deployment_summary(db: Session, since: datetime) -> dict:
    Project, _, Deployment, _, _ = _import_db_models()

    success_count = (
        db.query(Deployment)
        .filter(
            Deployment.kind == "deploy",
            Deployment.status == "success",
            Deployment.finished_at >= since,
        )
        .count()
    )

    failed_count = (
        db.query(Deployment)
        .filter(
            Deployment.kind == "deploy",
            Deployment.status == "failed",
            Deployment.finished_at >= since,
        )
        .count()
    )

    return {
        "success": success_count,
        "failed": failed_count,
    }


def _get_health_summary(db: Session) -> dict:
    Project, ProjectStatus, _, _, _ = _import_db_models()

    total = db.query(Project).count()

    projects_with_status = (
        db.query(Project)
        .outerjoin(ProjectStatus, Project.id == ProjectStatus.project_id)
        .all()
    )

    healthy = 0
    degraded = 0
    unhealthy = 0
    offline = 0
    stopped = 0

    for p in projects_with_status:
        health_status = p.status.health_status if p.status else "unknown"
        
        if health_status == "healthy":
            healthy += 1
        elif health_status == "degraded":
            degraded += 1
        elif health_status == "unhealthy":
            unhealthy += 1
        elif health_status == "stopped":
            stopped += 1
        
        if not p.status or _is_offline(p.status.agent_last_seen_at):
            offline += 1

    return {
        "total": total,
        "healthy": healthy,
        "degraded": degraded,
        "unhealthy": unhealthy,
        "offline": offline,
        "stopped": stopped,
    }


def _get_anomaly_projects(db: Session) -> List[AnomalyProject]:
    Project, ProjectStatus, Deployment, _, _ = _import_db_models()

    projects = (
        db.query(Project)
        .outerjoin(ProjectStatus, Project.id == ProjectStatus.project_id)
        .all()
    )

    anomaly_projects = []

    for project in projects:
        anomaly_types = []
        status = project.status
        health_status = status.health_status if status else "unknown"
        agent_last_seen_at = status.agent_last_seen_at if status else None

        if not status or _is_offline(agent_last_seen_at):
            anomaly_types.append("agent_offline")
        
        if health_status == "unhealthy":
            anomaly_types.append("health_unhealthy")
        elif health_status == "degraded":
            anomaly_types.append("health_degraded")

        last_deployment = (
            db.query(Deployment)
            .filter(
                Deployment.project_id == project.id,
                Deployment.kind.in_(("deploy", "rollback")),
            )
            .order_by(desc(Deployment.queued_at))
            .first()
        )

        last_deployment_status = last_deployment.status if last_deployment else None
        last_deployment_id = last_deployment.id if last_deployment else None
        last_deployment_at = last_deployment.finished_at or last_deployment.queued_at if last_deployment else None

        if last_deployment and last_deployment.status == "failed":
            anomaly_types.append("last_deploy_failed")

        if anomaly_types:
            anomaly_projects.append(AnomalyProject(
                project_id=project.id,
                project_name=project.name,
                anomaly_types=anomaly_types,
                health_status=health_status,
                agent_last_seen_at=agent_last_seen_at,
                last_deployment_status=last_deployment_status,
                last_deployment_id=last_deployment_id,
                last_deployment_at=last_deployment_at,
            ))

    anomaly_projects.sort(key=lambda x: (
        0 if "agent_offline" in x.anomaly_types else
        1 if "health_unhealthy" in x.anomaly_types else
        2 if "last_deploy_failed" in x.anomaly_types else 3,
        -(x.last_deployment_at.timestamp() if x.last_deployment_at else 0)
    ))

    return anomaly_projects


def _get_recent_changes(db: Session, limit: int = 30) -> List[ChangeEvent]:
    Project, _, Deployment, FlagAudit, WebhookDelivery = _import_db_models()

    changes = []

    deployments = (
        db.query(Deployment)
        .order_by(desc(Deployment.queued_at))
        .limit(limit)
        .all()
    )

    for d in deployments:
        if d.kind == "rollback":
            category = "rollback"
            event_type = f"rollback_{d.status}"
            title = f"Rollback {d.status}"
        elif d.kind in ("service_stop", "service_start"):
            category = "operation"
            event_type = f"operation_{d.status}"
            title = f"{'Stop' if d.kind == 'service_stop' else 'Start'} {d.status}"
        else:
            category = "deployment"
            event_type = f"deploy_{d.status}"
            title = f"Deploy {d.status}"
            if d.requested_services:
                title = f"Partial deploy ({', '.join(d.requested_services)}) {d.status}"
        
        summary_parts = []
        if d.commit_hash:
            summary_parts.append(f"Commit: {d.commit_hash[:8]}")
        if d.triggered_by:
            summary_parts.append(f"By: {d.triggered_by}")
        if d.trigger_source:
            summary_parts.append(f"Source: {d.trigger_source}")
        
        project = db.query(Project).filter(Project.id == d.project_id).first()
        
        changes.append({
            "event_category": category,
            "event_type": event_type,
            "occurred_at": d.finished_at or d.queued_at,
            "project_id": d.project_id,
            "project_name": project.name if project else "Unknown",
            "title": title,
            "summary": " | ".join(summary_parts) if summary_parts else None,
            "actor": d.triggered_by,
            "deployment_id": d.id,
            "flag_key": None,
        })

    flag_audits = (
        db.query(FlagAudit)
        .order_by(desc(FlagAudit.created_at))
        .limit(limit)
        .all()
    )

    for audit in flag_audits:
        project = db.query(Project).filter(Project.id == audit.project_id).first()
        
        if audit.old_enabled is None:
            title = f"Flag '{audit.flag_key}' created"
        else:
            action = "enabled" if audit.new_enabled else "disabled"
            title = f"Flag '{audit.flag_key}' {action}"
        
        changes.append({
            "event_category": "flag_audit",
            "event_type": "flag_changed",
            "occurred_at": audit.created_at,
            "project_id": audit.project_id,
            "project_name": project.name if project else "Unknown",
            "title": title,
            "summary": f"Changed by: {audit.changed_by}",
            "actor": audit.changed_by,
            "deployment_id": None,
            "flag_key": audit.flag_key,
        })

    webhook_deliveries = (
        db.query(WebhookDelivery)
        .order_by(desc(WebhookDelivery.created_at))
        .limit(limit)
        .all()
    )

    for delivery in webhook_deliveries:
        project = db.query(Project).filter(Project.id == delivery.project_id).first()
        
        changes.append({
            "event_category": "webhook",
            "event_type": f"webhook_{delivery.event_type}",
            "occurred_at": delivery.created_at,
            "project_id": delivery.project_id,
            "project_name": project.name if project else "Unknown",
            "title": f"Webhook {delivery.event_type}",
            "summary": f"Source: {delivery.source}",
            "actor": None,
            "deployment_id": None,
            "flag_key": None,
        })

    changes.sort(key=lambda x: x["occurred_at"], reverse=True)
    return [ChangeEvent(**c) for c in changes[:limit]]


@router.get("/summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)
    
    health_summary = _get_health_summary(db)
    deploy_summary = _get_deployment_summary(db, last_24h)
    anomaly_projects = _get_anomaly_projects(db)
    recent_changes = _get_recent_changes(db)

    return DashboardSummaryResponse(
        summary=DashboardSummary(
            total_projects=health_summary["total"],
            healthy_projects=health_summary["healthy"],
            degraded_projects=health_summary["degraded"],
            unhealthy_projects=health_summary["unhealthy"],
            offline_projects=health_summary["offline"],
            stopped_projects=health_summary["stopped"],
            last_24h_deployments_success=deploy_summary["success"],
            last_24h_deployments_failed=deploy_summary["failed"],
        ),
        anomaly_projects=anomaly_projects,
        recent_changes=recent_changes,
    )
