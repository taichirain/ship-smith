from typing import List, Optional
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..schemas import DeploymentResponse, DeploymentLogResponse


router = APIRouter(prefix="/deployments", tags=["deployments"])


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Deployment, DeploymentLog, ProjectTarget, DeploymentTarget
    return Deployment, DeploymentLog, ProjectTarget, DeploymentTarget


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, _ = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )
    
    return DeploymentResponse.model_validate(deployment)


@router.get("/{deployment_id}/logs", response_model=List[DeploymentLogResponse])
async def get_deployment_logs(
    deployment_id: int,
    after_seq: Optional[int] = Query(default=None, ge=0),
    limit: int = Query(default=1000, ge=1, le=5000),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, DeploymentLog = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    query = db.query(DeploymentLog).filter(DeploymentLog.deployment_id == deployment_id)
    
    if after_seq is not None:
        query = query.filter(DeploymentLog.seq > after_seq)
    
    logs = query.order_by(DeploymentLog.seq.asc()).limit(limit).all()
    return [DeploymentLogResponse.model_validate(l) for l in logs]


@router.get("/{deployment_id}/detail")
async def get_deployment_detail(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, DeploymentLog, ProjectTarget, DeploymentTarget = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    total_logs = (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment_id)
        .count()
    )

    last_log = (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.seq.desc())
        .first()
    )

    targets = (
        db.query(DeploymentTarget)
        .filter(DeploymentTarget.deployment_id == deployment_id)
        .order_by(DeploymentTarget.id.asc())
        .all()
    )

    targets_data = []
    success_count = 0
    failed_count = 0
    running_count = 0
    queued_count = 0
    blocked_count = 0
    cancelled_count = 0

    for t in targets:
        target_data = {
            "id": t.id,
            "deployment_id": t.deployment_id,
            "project_target_id": t.project_target_id,
            "agent_id": t.agent_id,
            "status": t.status,
            "commit_hash": t.commit_hash,
            "started_at": t.started_at.isoformat() if t.started_at else None,
            "finished_at": t.finished_at.isoformat() if t.finished_at else None,
            "error_code": t.error_code,
            "error_message": t.error_message,
            "last_heartbeat_at": t.last_heartbeat_at.isoformat() if t.last_heartbeat_at else None,
        }

        if t.status == "success" or t.status == "rolled_back":
            success_count += 1
        elif t.status == "failed" or t.status == "rollback_failed":
            failed_count += 1
        elif t.status == "running":
            running_count += 1
        elif t.status == "queued":
            queued_count += 1
        elif t.status == "blocked":
            blocked_count += 1
        elif t.status == "cancelled":
            cancelled_count += 1

        if t.project_target_id:
            pt = (
                db.query(ProjectTarget)
                .filter(ProjectTarget.id == t.project_target_id)
                .first()
            )
            if pt:
                target_data["target_name"] = pt.name
                target_data["target_role"] = pt.role
                target_data["target_order_index"] = pt.order_index

        targets_data.append(target_data)

    deployment_data = DeploymentResponse.model_validate(deployment).model_dump()
    deployment_data["failure_phase"] = deployment.failure_phase
    deployment_data["last_heartbeat_at"] = deployment.last_heartbeat_at
    deployment_data["lease_expires_at"] = deployment.lease_expires_at
    deployment_data["webhook_delivery_id"] = deployment.webhook_delivery_id
    deployment_data["total_logs"] = total_logs
    deployment_data["last_log_seq"] = last_log.seq if last_log else None
    deployment_data["targets"] = targets_data
    deployment_data["target_stats"] = {
        "total": len(targets),
        "success": success_count,
        "failed": failed_count,
        "running": running_count,
        "queued": queued_count,
        "blocked": blocked_count,
        "cancelled": cancelled_count,
    }

    return deployment_data


@router.post("/{deployment_id}/retry", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def retry_deployment(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, _, ProjectTarget, DeploymentTarget = _import_db_models()

    source_deployment = (
        db.query(Deployment)
        .filter(Deployment.id == deployment_id)
        .first()
    )
    if not source_deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source deployment not found",
        )

    if source_deployment.status not in ["failed", "cancelled"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed or cancelled deployments can be retried",
        )

    existing_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == source_deployment.project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )
    if existing_running:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another deployment is already in progress for this project",
        )

    enabled_targets = (
        db.query(ProjectTarget)
        .filter(
            ProjectTarget.project_id == source_deployment.project_id,
            ProjectTarget.enabled == True,
        )
        .order_by(ProjectTarget.order_index.asc(), ProjectTarget.id.asc())
        .all()
    )
    if not enabled_targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No enabled targets for this project",
        )

    deploy_mode = source_deployment.deploy_mode or "all-at-once"

    retry_deployment = Deployment(
        project_id=source_deployment.project_id,
        kind=source_deployment.kind,
        status="queued",
        deploy_mode=deploy_mode,
        trigger_source="retry",
        commit_hash=source_deployment.commit_hash,
        triggered_by=current_user.get("username"),
        queued_at=datetime.utcnow(),
        target_deployment_id=source_deployment.target_deployment_id,
    )
    db.add(retry_deployment)
    db.flush()

    for idx, target in enumerate(enabled_targets):
        dt_status = "queued"
        if deploy_mode == "rolling" and idx > 0:
            dt_status = "blocked"

        deployment_target = DeploymentTarget(
            deployment_id=retry_deployment.id,
            project_target_id=target.id,
            agent_id=target.agent_id,
            status=dt_status,
        )
        db.add(deployment_target)

    db.commit()
    db.refresh(retry_deployment)

    return DeploymentResponse.model_validate(retry_deployment)


@router.get("/{deployment_id}/failure-explanation")
async def get_deployment_failure_explanation(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, DeploymentLog = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    if deployment.status not in ["failed", "rollback_failed"]:
        return {
            "error": "This deployment did not fail",
            "status": deployment.status,
        }

    from ..failure_explainer import explain_failure

    logs = (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.seq.desc())
        .limit(200)
        .all()
    )

    log_excerpt = None
    if logs:
        log_excerpt = "\n".join([l.content for l in reversed(logs)])

    explanation = explain_failure(
        error_code=deployment.error_code,
        failure_phase=deployment.failure_phase,
        log_excerpt=log_excerpt,
    )

    return explanation


@router.get("/{deployment_id}/logs/download")
async def download_deployment_logs(
    deployment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Deployment, DeploymentLog = _import_db_models()

    deployment = db.query(Deployment).filter(Deployment.id == deployment_id).first()
    if not deployment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deployment not found",
        )

    logs = (
        db.query(DeploymentLog)
        .filter(DeploymentLog.deployment_id == deployment_id)
        .order_by(DeploymentLog.seq.asc())
        .all()
    )

    buffer = StringIO()

    header = f"Deployment #{deployment_id} - {deployment.kind} - {deployment.status}\n"
    header += f"Project ID: {deployment.project_id}\n"
    if deployment.commit_hash:
        header += f"Commit: {deployment.commit_hash}\n"
    if deployment.triggered_by:
        header += f"Triggered by: {deployment.triggered_by}\n"
    header += "-" * 60 + "\n\n"
    buffer.write(header)

    for log in logs:
        phase_str = f"[{log.phase or 'unknown'}]" if log.phase else ""
        timestamp_str = log.created_at.strftime("%Y-%m-%d %H:%M:%S") if log.created_at else ""
        prefix = f"{timestamp_str} {phase_str}".strip()
        if prefix:
            buffer.write(f"{prefix}  ")
        buffer.write(log.content)
        if not log.content.endswith("\n"):
            buffer.write("\n")

    buffer.seek(0)

    filename = f"deployment-{deployment_id}-logs.txt"

    return StreamingResponse(
        iter([buffer.read()]),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )

