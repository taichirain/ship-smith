import hashlib
from datetime import datetime

from shipsmith_db import Deployment, DeploymentTarget


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
