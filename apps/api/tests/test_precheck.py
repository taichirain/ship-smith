"""Precheck must reach the Agent, not just create a queued row."""

import hashlib
from datetime import datetime

from shipsmith_db import Deployment, DeploymentTarget, ProjectTarget


def _agent_headers(token: str = "agent-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bind_agent_token(test_session, test_project, token: str = "agent-token") -> None:
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_session.commit()


def test_precheck_creates_a_deployment_target(client, auth_headers, test_session, test_project):
    response = client.post(f"/api/v1/projects/{test_project.id}/precheck", headers=auth_headers)

    assert response.status_code == 202
    deployment_id = response.json()["deployment_id"]

    deployment = test_session.query(Deployment).filter(Deployment.id == deployment_id).one()
    assert deployment.kind == "precheck"
    assert deployment.status == "queued"

    targets = (
        test_session.query(DeploymentTarget)
        .filter(DeploymentTarget.deployment_id == deployment_id)
        .all()
    )
    assert len(targets) == 1
    assert targets[0].agent_id == test_project.agent_id
    assert targets[0].status == "queued"


def test_precheck_task_is_handed_to_its_agent(client, auth_headers, test_session, test_project):
    response = client.post(f"/api/v1/projects/{test_project.id}/precheck", headers=auth_headers)
    assert response.status_code == 202
    deployment_id = response.json()["deployment_id"]

    _bind_agent_token(test_session, test_project)
    polled = client.get("/api/v1/agents/tasks", headers=_agent_headers())

    assert polled.status_code == 200
    task = polled.json()["task"]
    assert task is not None
    assert task["id"] == deployment_id
    assert task["kind"] == "precheck"


def test_precheck_is_rejected_while_another_task_is_pending(
    client, auth_headers, test_session, test_project
):
    pending = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="queued",
        trigger_source="manual",
        queued_at=datetime.utcnow(),
    )
    test_session.add(pending)
    test_session.commit()

    response = client.post(f"/api/v1/projects/{test_project.id}/precheck", headers=auth_headers)

    assert response.status_code == 409


def test_precheck_requires_an_enabled_target(client, auth_headers, test_session, test_project):
    test_session.query(ProjectTarget).filter(
        ProjectTarget.project_id == test_project.id
    ).delete()
    test_session.commit()

    response = client.post(f"/api/v1/projects/{test_project.id}/precheck", headers=auth_headers)

    assert response.status_code == 400
