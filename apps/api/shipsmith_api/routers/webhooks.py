import hashlib
import hmac
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..deps import get_db


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Project, Deployment, WebhookDelivery
    return Project, Deployment, WebhookDelivery


def _verify_github_signature(payload_bytes: bytes, secret: str, signature_header: str) -> bool:
    if not secret:
        return True
    
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    
    received_signature = signature_header[len("sha256="):]
    
    mac = hmac.new(secret.encode(), payload_bytes, hashlib.sha256)
    expected_signature = mac.hexdigest()
    
    return hmac.compare_digest(received_signature, expected_signature)


def _verify_gitlab_token(secret: str, token_header: Optional[str]) -> bool:
    if not secret:
        return True
    
    return token_header == secret


def _find_project_by_webhook_endpoint(db: Session, endpoint_id: str) -> Optional[object]:
    Project, _, _ = _import_db_models()
    return db.query(Project).filter(Project.webhook_endpoint_id == endpoint_id).first()


def _find_project_by_repo(db: Session, repo_url: str) -> Optional[object]:
    Project, _, _ = _import_db_models()

    projects = db.query(Project).all()

    for project in projects:
        normalized_project = project.git_repo.lower().strip()
        normalized_input = repo_url.lower().strip()

        if normalized_project == normalized_input:
            return project

        normalized_project = normalized_project.replace(".git", "")
        normalized_input = normalized_input.replace(".git", "")

        if normalized_project == normalized_input:
            return project

        if normalized_project.endswith(normalized_input):
            return project
        if normalized_input.endswith(normalized_project):
            return project

    return None


def _is_delivery_processed(db: Session, project_id: int, delivery_id: str) -> bool:
    _, _, WebhookDelivery = _import_db_models()
    
    existing = (
        db.query(WebhookDelivery)
        .filter(
            WebhookDelivery.project_id == project_id,
            WebhookDelivery.delivery_id == delivery_id,
        )
        .first()
    )
    return existing is not None


def _record_delivery(db: Session, project_id: int, delivery_id: str, event_type: str, source: str, payload: dict):
    _, _, WebhookDelivery = _import_db_models()
    
    delivery = WebhookDelivery(
        project_id=project_id,
        delivery_id=delivery_id,
        event_type=event_type,
        source=source,
        payload=payload,
        created_at=datetime.utcnow(),
    )
    db.add(delivery)
    db.commit()


def _create_deployment_for_project(db: Session, project_id: int, commit_hash: Optional[str], ref: Optional[str] = None, delivery_id: Optional[str] = None):
    _, Deployment, _ = _import_db_models()

    existing_queued_or_running = (
        db.query(Deployment)
        .filter(
            Deployment.project_id == project_id,
            Deployment.status.in_(["queued", "running"]),
        )
        .first()
    )

    if existing_queued_or_running:
        return existing_queued_or_running, False, "Another deployment is already in progress"

    deployment = Deployment(
        project_id=project_id,
        kind="deploy",
        status="queued",
        trigger_source="webhook",
        commit_hash=commit_hash[:40] if commit_hash else None,
        webhook_delivery_id=delivery_id,
        triggered_by="webhook",
    )
    db.add(deployment)
    db.commit()
    db.refresh(deployment)

    return deployment, True, None


def _extract_branch_from_ref(ref: Optional[str]) -> Optional[str]:
    if not ref:
        return None
    if ref.startswith("refs/heads/"):
        return ref[len("refs/heads/"):]
    return ref


@router.post("/github")
async def github_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    Project, _, _ = _import_db_models()

    event = request.headers.get("X-GitHub-Event", "")
    delivery = request.headers.get("X-GitHub-Delivery", "")
    signature_256 = request.headers.get("X-Hub-Signature-256", "")

    payload_bytes = await request.body()
    payload = await request.json()

    ref = payload.get("ref", "")
    commits = payload.get("commits", [])
    head_commit = payload.get("head_commit")
    deleted = payload.get("deleted", False)

    repo = payload.get("repository", {})
    clone_url = repo.get("clone_url") or repo.get("ssh_url") or ""
    full_name = repo.get("full_name", "")

    if event == "ping":
        return {"ok": True, "event": "ping", "message": "pong"}

    if deleted:
        return {"ok": True, "event": event, "message": "Deleted branch event ignored"}

    if event != "push":
        return {"ok": False, "event": event, "message": "Only push events are processed"}

    if not clone_url and full_name:
        clone_url = f"git@github.com:{full_name}.git"

    if not clone_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository URL not found in payload",
        )

    project = _find_project_by_repo(db, clone_url)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found for repository: {clone_url}",
        )

    if not _verify_github_signature(payload_bytes, project.webhook_secret or "", signature_256):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    if _is_delivery_processed(db, project.id, delivery):
        return {
            "ok": True,
            "event": event,
            "delivery": delivery,
            "project_id": project.id,
            "project_name": project.name,
            "created": False,
            "message": "Delivery already processed (idempotent)",
        }

    branch = _extract_branch_from_ref(ref)
    if branch and project.git_branch and branch != project.git_branch:
        _record_delivery(db, project.id, delivery, event, "github", payload)
        return {
            "ok": True,
            "event": event,
            "delivery": delivery,
            "project_id": project.id,
            "project_name": project.name,
            "created": False,
            "message": f"Branch '{branch}' does not match target branch '{project.git_branch}'",
        }

    commit_hash = None
    if head_commit:
        commit_hash = head_commit.get("id")
    elif commits and len(commits) > 0:
        commit_hash = commits[-1].get("id")

    deployment, created, message = _create_deployment_for_project(db, project.id, commit_hash, ref, delivery)
    _record_delivery(db, project.id, delivery, event, "github", payload)

    return {
        "ok": True,
        "event": event,
        "delivery": delivery,
        "project_id": project.id,
        "project_name": project.name,
        "deployment_id": deployment.id,
        "created": created,
        "commit_hash": commit_hash,
        "ref": ref,
        "message": message,
    }


@router.post("/gitlab")
async def gitlab_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    Project, _, _ = _import_db_models()

    event = request.headers.get("X-Gitlab-Event", "")
    token = request.headers.get("X-Gitlab-Token", "")

    payload = await request.json()

    event_name = payload.get("event_name", payload.get("object_kind", ""))
    ref = payload.get("ref", "")
    commit_hash = payload.get("checkout_sha") or payload.get("after")
    before = payload.get("before", "0000000000000000000000000000000000000000")
    after = payload.get("after", "0000000000000000000000000000000000000000")

    project_payload = payload.get("project", {})
    git_http_url = project_payload.get("git_http_url")
    git_ssh_url = project_payload.get("git_ssh_url")
    web_url = project_payload.get("web_url")

    clone_url = git_ssh_url or git_http_url or web_url or ""

    if event_name == "ping" or event_name == "system_hook":
        return {"ok": True, "event": event, "message": "pong"}

    if event_name != "push":
        return {"ok": False, "event": event, "event_name": event_name, "message": "Only push events are processed"}

    if before == after and before != "0000000000000000000000000000000000000000":
        return {"ok": True, "message": "No actual changes (force push to same commit?)"}

    if after == "0000000000000000000000000000000000000000":
        return {"ok": True, "message": "Deleted branch event ignored"}

    if not clone_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository URL not found in payload",
        )

    project = _find_project_by_repo(db, clone_url)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project not found for repository: {clone_url}",
        )

    if not _verify_gitlab_token(project.webhook_secret or "", token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook token",
        )

    delivery_id = f"{before[:8]}-{after[:8]}-{ref}"
    if _is_delivery_processed(db, project.id, delivery_id):
        return {
            "ok": True,
            "event": event,
            "project_id": project.id,
            "project_name": project.name,
            "created": False,
            "message": "Delivery already processed (idempotent)",
        }

    branch = _extract_branch_from_ref(ref)
    if branch and project.git_branch and branch != project.git_branch:
        _record_delivery(db, project.id, delivery_id, event_name, "gitlab", payload)
        return {
            "ok": True,
            "event": event,
            "project_id": project.id,
            "project_name": project.name,
            "created": False,
            "message": f"Branch '{branch}' does not match target branch '{project.git_branch}'",
        }

    deployment, created, message = _create_deployment_for_project(db, project.id, commit_hash, ref, delivery_id)
    _record_delivery(db, project.id, delivery_id, event_name, "gitlab", payload)

    return {
        "ok": True,
        "event": event,
        "project_id": project.id,
        "project_name": project.name,
        "deployment_id": deployment.id,
        "created": created,
        "commit_hash": commit_hash,
        "ref": ref,
        "message": message,
    }


@router.post("/{webhook_endpoint_id}/github")
async def github_webhook_by_endpoint(
    webhook_endpoint_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    project = _find_project_by_webhook_endpoint(db, webhook_endpoint_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )
    
    return await github_webhook(request, db)


@router.post("/{webhook_endpoint_id}/gitlab")
async def gitlab_webhook_by_endpoint(
    webhook_endpoint_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    project = _find_project_by_webhook_endpoint(db, webhook_endpoint_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook endpoint not found",
        )
    
    return await gitlab_webhook(request, db)
