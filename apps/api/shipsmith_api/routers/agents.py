import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_agent
from ..schemas import DeploymentResponse
from ..security import decrypt_secret
from ..monitor import DETECTED_OFFLINE_KEY, check_agent_offline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

TASK_LEASE_DURATION_SECONDS = 300


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Deployment, Project, Heartbeat, ProjectStatus, DeploymentTarget, ProjectTarget
    return Deployment, Project, Heartbeat, ProjectStatus, DeploymentTarget, ProjectTarget


def _get_now() -> datetime:
    return datetime.utcnow()


def _get_lease_expires_at() -> datetime:
    return _get_now() + timedelta(seconds=TASK_LEASE_DURATION_SECONDS)


def _cleanup_expired_tasks(db: Session):
    Deployment, _, _, _, DeploymentTarget, _ = _import_db_models()
    now = _get_now()

    expired_running = (
        db.query(DeploymentTarget)
        .filter(
            DeploymentTarget.status == "running",
            DeploymentTarget.lease_expires_at.isnot(None),
            DeploymentTarget.lease_expires_at < now,
        )
        .all()
    )

    affected_deployments = set()
    for dt in expired_running:
        dt.status = "failed"
        dt.error_code = "agent_disconnected"
        dt.error_message = "Task lease expired. Agent may have crashed or lost connectivity."
        dt.finished_at = now
        dt.lease_expires_at = None
        affected_deployments.add(dt.deployment_id)

    db.flush()
    for deployment_id in affected_deployments:
        _advance_rolling_deployment(db, deployment_id)
        db.flush()
        deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
        if not deployment:
            continue
        deployment.status = _aggregate_deployment_status(db, deployment_id)
        if deployment.status in {"failed", "rollback_failed"}:
            deployment.error_code = "agent_disconnected"
            deployment.failure_phase = deployment.failure_phase or "agent_lease"
            deployment.finished_at = now
            deployment.lease_expires_at = None
            deployment.log_excerpt = (deployment.log_excerpt or "") + "\nERROR: Agent task lease expired."

    db.commit()


@router.get("/config")
async def get_agent_config(
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    _, Project, _, _, _, _ = _import_db_models()
    project = db.query(Project).filter(Project.id == current_agent["project_id"]).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return {
        "project_id": project.id,
        "project_name": project.name,
        "healthcheck_url": project.healthcheck_url,
        "healthcheck_timeout_seconds": project.healthcheck_timeout_seconds,
        "healthcheck_expected_status": project.healthcheck_expected_status,
    }


@router.get("/tasks")
async def poll_task(
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    Deployment, Project, _, ProjectStatus, DeploymentTarget, _ = _import_db_models()

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]

    _cleanup_expired_tasks(db)

    project_status = (
        db.query(ProjectStatus)
        .filter(ProjectStatus.project_id == project_id)
        .first()
    )
    if project_status:
        project_status.agent_last_seen_at = _get_now()
        project_status.updated_at = _get_now()
        db.commit()

    check_agent_offline(db, project_id)

    deployment_target = (
        db.query(DeploymentTarget)
        .join(Deployment, DeploymentTarget.deployment_id == Deployment.id)
        .filter(
            Deployment.project_id == project_id,
            DeploymentTarget.agent_id == agent_id,
            DeploymentTarget.status == "queued",
        )
        .order_by(Deployment.queued_at.asc(), DeploymentTarget.id.asc())
        .first()
    )

    if deployment_target is None:
        return {"task": None, "message": "No pending tasks"}

    deployment = (
        db.query(Deployment)
        .filter(Deployment.id == deployment_target.deployment_id)
        .first()
    )
    project = db.query(Project).filter(Project.id == project_id).first()

    return {
        "task": {
            "id": deployment.id,
            "deployment_target_id": deployment_target.id,
            "project_id": deployment.project_id,
            "kind": deployment.kind,
            "commit_hash": deployment.commit_hash,
            "target_commit_hash": None,
            "deploy_strategy": project.deploy_strategy if project else "compose-build",
            "git_branch": project.git_branch if project else "main",
            "git_repo": project.git_repo if project else None,
            "git_credential_type": project.git_credential_type if project else "none",
            "git_credential_username": project.git_credential_username if project else None,
            "git_credential_token": decrypt_secret(project.git_credential_token_encrypted) if project else None,
            "git_credential_ssh_private_key": decrypt_secret(project.git_credential_ssh_private_key_encrypted) if project else None,
            "git_credential_ssh_known_hosts": project.git_credential_ssh_known_hosts if project else None,
            "compose_file": project.compose_file if project else "docker-compose.yml",
            "compose_service": project.compose_service if project else "app",
            "healthcheck_url": project.healthcheck_url if project else None,
            "healthcheck_timeout_seconds": project.healthcheck_timeout_seconds if project else 10,
            "healthcheck_expected_status": project.healthcheck_expected_status if project else 200,
            "flags_file_path": project.flags_file_path if project else None,
            "migration_service": project.migration_service if project else "",
            "migration_command": project.migration_command if project else None,
            "migration_timeout_seconds": project.migration_timeout_seconds if project else 600,
            "migration_no_deps": project.migration_no_deps if project else True,
            "compose_profiles": project.compose_profiles if project else [],
            "pre_deploy_command": project.pre_deploy_command if project else None,
            "post_deploy_command": project.post_deploy_command if project else None,
            "created_at": deployment.queued_at.isoformat() if deployment.queued_at else None,
        },
        "message": "Task available",
    }


@router.post("/tasks/{task_id}/start")
async def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    Deployment, _, _, _, DeploymentTarget, _ = _import_db_models()

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.id == task_id,
            Deployment.project_id == project_id,
        )
        .first()
    )

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    deployment_target = (
        db.query(DeploymentTarget)
        .filter(
            DeploymentTarget.deployment_id == task_id,
            DeploymentTarget.agent_id == agent_id,
        )
        .first()
    )

    if not deployment_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No target task found for this agent",
        )

    if deployment_target.status != "queued":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task is already in state: {deployment_target.status}",
        )

    now = _get_now()
    deployment_target.status = "running"
    deployment_target.started_at = now
    deployment_target.lease_expires_at = _get_lease_expires_at()
    deployment_target.last_heartbeat_at = now

    if deployment.status == "queued":
        deployment.status = "running"
        deployment.started_at = now

    db.commit()
    db.refresh(deployment_target)
    db.refresh(deployment)

    return {
        "ok": True,
        "task_id": deployment.id,
        "deployment_target_id": deployment_target.id,
        "status": deployment_target.status,
        "started_at": deployment_target.started_at.isoformat() if deployment_target.started_at else None,
        "lease_expires_at": deployment_target.lease_expires_at.isoformat() if deployment_target.lease_expires_at else None,
    }


@router.post("/tasks/{task_id}/heartbeat")
async def refresh_task_heartbeat(
    task_id: int,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    Deployment, _, _, _, DeploymentTarget, _ = _import_db_models()

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.id == task_id,
            Deployment.project_id == project_id,
        )
        .first()
    )

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    deployment_target = (
        db.query(DeploymentTarget)
        .filter(
            DeploymentTarget.deployment_id == task_id,
            DeploymentTarget.agent_id == agent_id,
            DeploymentTarget.status == "running",
        )
        .first()
    )

    if not deployment_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or not running for this agent",
        )

    now = _get_now()
    deployment_target.last_heartbeat_at = now
    deployment_target.lease_expires_at = _get_lease_expires_at()
    deployment.last_heartbeat_at = now
    db.commit()
    db.refresh(deployment_target)

    return {
        "ok": True,
        "task_id": task_id,
        "deployment_target_id": deployment_target.id,
        "last_heartbeat_at": now.isoformat(),
        "lease_expires_at": deployment_target.lease_expires_at.isoformat() if deployment_target.lease_expires_at else None,
    }


@router.post("/tasks/{task_id}/logs")
async def append_task_logs(
    task_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    Deployment, _, _, _, DeploymentTarget, _ = _import_db_models()
    from shipsmith_db import DeploymentLog

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.id == task_id,
            Deployment.project_id == project_id,
        )
        .first()
    )

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    deployment_target = (
        db.query(DeploymentTarget)
        .filter(
            DeploymentTarget.deployment_id == task_id,
            DeploymentTarget.agent_id == agent_id,
        )
        .first()
    )

    if not deployment_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No target task found for this agent",
        )

    seq = data.get("seq", 0)
    phase = data.get("phase")

    existing = (
        db.query(DeploymentLog)
        .filter(
            DeploymentLog.deployment_id == task_id,
            DeploymentLog.deployment_target_id == deployment_target.id,
            DeploymentLog.seq == seq,
        )
        .first()
    )

    if existing:
        existing.content = data.get("content", existing.content)
        existing.phase = phase or existing.phase
    else:
        log = DeploymentLog(
            deployment_id=task_id,
            deployment_target_id=deployment_target.id,
            seq=seq,
            phase=phase,
            content=data.get("content", ""),
        )
        db.add(log)

    if data.get("content"):
        if not deployment.log_excerpt:
            deployment.log_excerpt = data["content"][:1000]
        elif len(deployment.log_excerpt) < 2000:
            deployment.log_excerpt += "\n" + data["content"][:500]

    if deployment_target.status == "running":
        now = _get_now()
        deployment_target.last_heartbeat_at = now
        deployment_target.lease_expires_at = _get_lease_expires_at()
        deployment.last_heartbeat_at = now

    db.commit()

    return {"ok": True, "seq": seq, "deployment_target_id": deployment_target.id}


def _aggregate_deployment_status(db: Session, deployment_id: int) -> str:
    from sqlalchemy import func
    Deployment, _, _, _, DeploymentTarget, _ = _import_db_models()

    targets = (
        db.query(DeploymentTarget)
        .filter(DeploymentTarget.deployment_id == deployment_id)
        .all()
    )

    if not targets:
        return "queued"

    statuses = [t.status for t in targets]

    if any(s == "running" for s in statuses):
        return "running"
    if any(s in ["queued", "blocked"] for s in statuses):
        return "running"
    if any(s == "failed" for s in statuses):
        return "failed"
    if all(s in ["success", "rolled_back"] for s in statuses):
        first_target = targets[0]
        if first_target.status == "rolled_back":
            return "rolled_back"
        return "success"
    if any(s == "rollback_failed" for s in statuses):
        return "rollback_failed"

    return "failed"


def _advance_rolling_deployment(db: Session, deployment_id: int):
    Deployment, _, _, _, DeploymentTarget, ProjectTarget = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment or deployment.deploy_mode != "rolling":
        return

    targets = (
        db.query(DeploymentTarget)
        .outerjoin(ProjectTarget, DeploymentTarget.project_target_id == ProjectTarget.id)
        .filter(DeploymentTarget.deployment_id == deployment_id)
        .order_by(ProjectTarget.order_index.asc().nullslast(), DeploymentTarget.id.asc())
        .all()
    )

    previous_failed = False
    for target in targets:
        if previous_failed and target.status == "blocked":
            target.status = "cancelled"
            continue

        if target.status == "blocked":
            target.status = "queued"
            return

        if target.status == "failed":
            previous_failed = True


@router.post("/tasks/{task_id}/finish")
async def finish_task(
    task_id: int,
    data: dict,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    Deployment, _, _, ProjectStatus, DeploymentTarget, _ = _import_db_models()

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]

    deployment = (
        db.query(Deployment)
        .filter(
            Deployment.id == task_id,
            Deployment.project_id == project_id,
        )
        .first()
    )

    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    deployment_target = (
        db.query(DeploymentTarget)
        .filter(
            DeploymentTarget.deployment_id == task_id,
            DeploymentTarget.agent_id == agent_id,
        )
        .first()
    )

    if not deployment_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No target task found for this agent",
        )

    status_value = data.get("status")
    valid_statuses = ["success", "failed", "rolled_back", "rollback_failed"]
    if status_value not in valid_statuses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Must be one of: {valid_statuses}",
        )

    now = _get_now()
    deployment_target.status = status_value
    deployment_target.commit_hash = data.get("commit_hash") or deployment_target.commit_hash
    deployment_target.error_code = data.get("error_code")
    deployment_target.error_message = data.get("error_message")
    deployment_target.failure_phase = data.get("failure_phase") or deployment_target.failure_phase
    if data.get("target_commit_hash"):
        deployment_target.target_commit_hash = data.get("target_commit_hash")
    if data.get("previous_commit_hash"):
        deployment_target.previous_commit_hash = data.get("previous_commit_hash")
    if data.get("image_snapshot") is not None:
        deployment_target.image_snapshot = data.get("image_snapshot")
    if data.get("health_result") is not None:
        deployment_target.health_result = data.get("health_result")
    deployment_target.finished_at = now
    deployment_target.lease_expires_at = None

    if deployment.deploy_mode == "rolling" and status_value == "success":
        _advance_rolling_deployment(db, deployment.id)
    elif deployment.deploy_mode == "rolling" and status_value == "failed":
        _advance_rolling_deployment(db, deployment.id)

    deployment.commit_hash = data.get("commit_hash") or data.get("target_commit_hash") or deployment.commit_hash
    if data.get("previous_commit_hash"):
        deployment.previous_commit_hash = data.get("previous_commit_hash")
    if data.get("image_snapshot") is not None:
        deployment.image_snapshot = data.get("image_snapshot")
    if data.get("health_result") is not None:
        deployment.health_result = data.get("health_result")
    if data.get("error_code"):
        deployment.error_code = data.get("error_code")
    if data.get("error_message"):
        deployment.log_excerpt = (deployment.log_excerpt or "") + "\nERROR: " + data.get("error_message")[:1000]
    if data.get("failure_phase"):
        deployment.failure_phase = str(data.get("failure_phase"))[:32]

    db.flush()

    overall_status = _aggregate_deployment_status(db, deployment.id)
    deployment.status = overall_status

    if overall_status in ["success", "failed", "rolled_back", "rollback_failed"]:
        deployment.finished_at = now
        deployment.lease_expires_at = None

    if overall_status in ["success", "rolled_back"]:
        project_status = (
            db.query(ProjectStatus)
            .filter(ProjectStatus.project_id == project_id)
            .first()
        )
        if project_status:
            project_status.last_deployment_id = deployment.id
            project_status.current_commit_hash = deployment.commit_hash
            project_status.updated_at = now

    db.commit()
    db.refresh(deployment)
    db.refresh(deployment_target)

    if overall_status in ["success", "failed", "rolled_back", "rollback_failed"]:
        event_type = None
        if overall_status in ["success", "rolled_back"]:
            event_type = "deployment_success"
        else:
            event_type = "deployment_failed"

        event_details = None
        try:
            from ..notifications import get_event_details_for_deployment
            event_details = get_event_details_for_deployment(deployment)
        except Exception:
            pass

        if event_details:
            if event_type == "deployment_failed":
                try:
                    from ..alerts import create_or_update_alert
                    create_or_update_alert(db, project_id, "deployment_failed", event_details)
                except Exception:
                    pass
            else:
                try:
                    from ..alerts import resolve_alert_by_fingerprint
                    resolve_alert_by_fingerprint(db, project_id, "deployment_failed", event_details)
                except Exception:
                    pass

            try:
                from ..notifications import dispatch_notification
                dispatch_notification(db, project_id, event_type, event_details)
            except Exception:
                pass

    return {
        "ok": True,
        "task_id": deployment.id,
        "deployment_target_id": deployment_target.id,
        "status": deployment_target.status,
        "overall_status": overall_status,
        "finished_at": deployment_target.finished_at.isoformat() if deployment_target.finished_at else None,
    }


@router.post("/heartbeat")
async def agent_heartbeat(
    data: dict,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    _, _, Heartbeat, ProjectStatus, _, _ = _import_db_models()

    project_id = current_agent["project_id"]
    agent_id = current_agent["agent_id"]
    now = _get_now()

    heartbeat = Heartbeat(
        project_id=project_id,
        agent_id=agent_id,
        payload=data,
    )
    db.add(heartbeat)

    project_status = (
        db.query(ProjectStatus)
        .filter(ProjectStatus.project_id == project_id)
        .first()
    )

    event_to_send = None
    event_details = None
    old_health_status = None
    new_health_status = "unknown"

    if project_status:
        old_health_status = project_status.health_status
        previous_snapshot = project_status.snapshot if isinstance(project_status.snapshot, dict) else {}
        detected_offline_at = previous_snapshot.get(DETECTED_OFFLINE_KEY)
        project_status.agent_last_seen_at = now
        if project_status.agent_first_seen_at is None:
            project_status.agent_first_seen_at = now
        app_health = data.get("app_health", {}) if isinstance(data, dict) else {}
        new_health_status = "unknown"
        if isinstance(app_health, dict):
            status_val = app_health.get("status", "unknown")
            if status_val in ["healthy", "degraded", "unhealthy", "unknown"]:
                new_health_status = status_val
                project_status.health_status = status_val
        project_status.snapshot = data
        if detected_offline_at and isinstance(project_status.snapshot, dict):
            project_status.snapshot[DETECTED_OFFLINE_KEY] = detected_offline_at
        project_status.updated_at = now
        
        if old_health_status and old_health_status != new_health_status:
            if old_health_status in ["degraded", "unhealthy"] and new_health_status == "healthy":
                event_to_send = "health_recovered"
                event_details = {
                    "agent_id": agent_id,
                    "old_status": old_health_status,
                    "new_status": new_health_status,
                }
            elif new_health_status == "degraded":
                event_to_send = "health_degraded"
                event_details = {
                    "agent_id": agent_id,
                    "old_status": old_health_status,
                    "new_status": new_health_status,
                }
            elif new_health_status == "unhealthy":
                event_to_send = "health_unhealthy"
                event_details = {
                    "agent_id": agent_id,
                    "old_status": old_health_status,
                    "new_status": new_health_status,
                }

    db.commit()

    if project_status and old_health_status != new_health_status:
        logger.info(
            "project %s health changed: %s -> %s",
            project_id,
            old_health_status,
            new_health_status,
        )

    try:
        check_agent_offline(db, project_id)
    except Exception:
        pass

    if project_status and new_health_status == "healthy":
        try:
            from ..alerts import resolve_alert_by_fingerprint

            resolved = resolve_alert_by_fingerprint(
                db,
                project_id,
                "health_unhealthy",
                {"agent_id": agent_id},
            )
            if resolved:
                logger.info("resolved %s health alert(s) for project %s", len(resolved), project_id)
        except Exception:
            logger.exception("failed to resolve health alerts for project %s", project_id)

    if event_to_send and event_details:
        if event_to_send == "health_unhealthy":
            try:
                from ..alerts import create_or_update_alert
                create_or_update_alert(db, project_id, "health_unhealthy", event_details)
            except Exception:
                pass
        elif event_to_send == "health_recovered":
            try:
                from ..alerts import resolve_alert_by_fingerprint
                resolve_alert_by_fingerprint(db, project_id, "health_unhealthy", event_details)
            except Exception:
                pass

        try:
            from ..notifications import dispatch_notification
            dispatch_notification(db, project_id, event_to_send, event_details)
        except Exception:
            pass

    return {
        "received": True,
        "server_time": now.isoformat(),
    }


@router.get("/flags/sync")
async def sync_flags(
    current_version: int = 0,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    _, Project, _, _, _, _ = _import_db_models()
    from shipsmith_db import FeatureFlag

    project_id = current_agent["project_id"]
    project = db.query(Project).filter(Project.id == project_id).first()

    flags = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.project_id == project_id,
            FeatureFlag.archived == False,
        )
        .all()
    )

    max_version = max((f.version for f in flags), default=0)

    if max_version == current_version:
        return {
            "version": current_version,
            "flags": None,
            "changed": False,
            "flags_file_path": project.flags_file_path if project else None,
        }

    flags_dict = {f.key: f.enabled for f in flags}

    return {
        "version": max_version,
        "flags": flags_dict,
        "changed": True,
        "flags_file_path": project.flags_file_path if project else None,
    }


@router.post("/prechecks/result")
async def save_precheck_result(
    data: dict,
    db: Session = Depends(get_db),
    current_agent: dict = Depends(get_current_agent),
):
    from shipsmith_db import AgentPrecheck, Deployment

    project_id = current_agent["project_id"]
    agent_id = current_agent.get("agent_id", "unknown")

    precheck_result = data.get("precheck_result", {})
    summary = precheck_result.get("summary", {})

    precheck = AgentPrecheck(
        project_id=project_id,
        agent_id=agent_id,
        overall_status=precheck_result.get("overall_status", "unknown"),
        summary=summary,
        result_json=precheck_result,
        started_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
    )
    db.add(precheck)
    db.commit()
    db.refresh(precheck)

    return {
        "ok": True,
        "precheck_id": precheck.id,
    }
