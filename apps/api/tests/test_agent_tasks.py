import hashlib
from datetime import datetime, timedelta

from shipsmith_db import Deployment, DeploymentTarget
from shipsmith_api.routers.agents import _cleanup_expired_tasks


def _agent_headers(token: str = "agent-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bind_agent_token(test_session, test_project, token: str = "agent-token") -> None:
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_session.commit()


def test_finish_task_persists_failure_phase(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="running",
        trigger_source="manual",
        commit_hash="abc123",
        queued_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )
    test_session.add(deployment)
    test_session.flush()
    target = DeploymentTarget(
        deployment_id=deployment.id,
        agent_id=test_project.agent_id,
        status="running",
    )
    test_session.add(target)
    test_session.commit()

    response = client.post(
        f"/api/v1/agents/tasks/{deployment.id}/finish",
        headers=_agent_headers(),
        json={
            "status": "failed",
            "error_code": "docker_build_failed",
            "error_message": "build failed",
            "failure_phase": "docker_build",
        },
    )
    assert response.status_code == 200
    test_session.refresh(deployment)
    assert deployment.failure_phase == "docker_build"
    assert deployment.status == "failed"


def test_agent_flags_sync_returns_flags_file_path(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    response = client.get(
        "/api/v1/agents/flags/sync",
        headers=_agent_headers(),
        params={"current_version": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["flags_file_path"] == test_project.flags_file_path


def test_expired_agent_task_fails_parent_deployment(test_session, test_project):
    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="running",
        trigger_source="manual",
        commit_hash="abc123",
        queued_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )
    test_session.add(deployment)
    test_session.flush()
    target = DeploymentTarget(
        deployment_id=deployment.id,
        agent_id=test_project.agent_id,
        status="running",
        lease_expires_at=datetime.utcnow() - timedelta(seconds=1),
    )
    test_session.add(target)
    test_session.commit()

    _cleanup_expired_tasks(test_session)
    test_session.refresh(target)
    test_session.refresh(deployment)
    assert target.status == "failed"
    assert target.error_code == "agent_disconnected"
    assert target.lease_expires_at is None
    assert deployment.status == "failed"
    assert deployment.error_code == "agent_disconnected"
    assert deployment.finished_at is not None
