import hashlib
from datetime import datetime

from shipsmith_db import Deployment, ProjectStatus


def _bind_agent_token(test_session, test_project, token="agent-token"):
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_session.commit()


def _agent_headers(token="agent-token"):
    return {"Authorization": f"Bearer {token}"}


def _finish_task(client, test_session, test_project, deployment, status="success"):
    _bind_agent_token(test_session, test_project)
    response = client.post(
        f"/api/v1/agents/tasks/{deployment.id}/finish",
        headers=_agent_headers(),
        json={"status": status},
    )
    assert response.status_code == 200


def test_stop_creates_service_task_and_sets_flag(client, auth_headers, test_project, test_session):
    response = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == "service_stop"
    assert data["status"] == "queued"

    status = test_session.get(ProjectStatus, test_project.id)
    assert status.intentionally_stopped is False

    _finish_task(client, test_session, test_project, test_session.get(Deployment, data["id"]))
    test_session.refresh(status)
    assert status.intentionally_stopped is True


def test_stop_twice_is_conflict(client, auth_headers, test_project, test_session):
    response = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    assert response.status_code == 201
    _finish_task(client, test_session, test_project, test_session.get(Deployment, response.json()["id"]))

    again = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    assert again.status_code == 409


def test_start_requires_stopped_state(client, auth_headers, test_project):
    response = client.post(f"/api/v1/projects/{test_project.id}/start", headers=auth_headers)
    assert response.status_code == 409


def test_start_clears_flag_after_success(client, auth_headers, test_project, test_session):
    stop = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    _finish_task(client, test_session, test_project, test_session.get(Deployment, stop.json()["id"]))

    start = client.post(f"/api/v1/projects/{test_project.id}/start", headers=auth_headers)
    assert start.status_code == 201
    assert start.json()["kind"] == "service_start"

    _finish_task(client, test_session, test_project, test_session.get(Deployment, start.json()["id"]))
    status = test_session.get(ProjectStatus, test_project.id)
    assert status.intentionally_stopped is False


def test_stop_task_shares_project_lock(client, auth_headers, test_project):
    client.post(f"/api/v1/projects/{test_project.id}/deploy", headers=auth_headers, json={"trigger_source": "manual"})
    response = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    assert response.status_code == 409


def test_successful_deploy_clears_intentional_stop(client, auth_headers, test_project, test_session):
    stop = client.post(f"/api/v1/projects/{test_project.id}/stop", headers=auth_headers)
    _finish_task(client, test_session, test_project, test_session.get(Deployment, stop.json()["id"]))
    status = test_session.get(ProjectStatus, test_project.id)
    assert status.intentionally_stopped is True

    deploy = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={"trigger_source": "manual"},
    )
    assert deploy.status_code == 201
    _finish_task(client, test_session, test_project, test_session.get(Deployment, deploy.json()["id"]))
    test_session.refresh(status)
    assert status.intentionally_stopped is False


def test_agent_config_reports_intentionally_stopped(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    status = test_session.get(ProjectStatus, test_project.id)
    status.intentionally_stopped = True
    test_session.commit()

    response = client.get("/api/v1/agents/config", headers=_agent_headers())
    assert response.status_code == 200
    assert response.json()["intentionally_stopped"] is True
