import hashlib
from datetime import datetime

from shipsmith_db import Deployment, DeploymentTarget


def _agent_headers(token: str = "agent-token") -> dict:
    return {"Authorization": f"Bearer {token}"}


def _bind_agent_token(test_session, test_project, token: str = "agent-token") -> None:
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_session.commit()


def test_request_logs_creates_task_and_target(client, auth_headers, test_session, test_project):
    response = client.post(f"/api/v1/projects/{test_project.id}/logs", headers=auth_headers)

    assert response.status_code == 202
    deployment_id = response.json()["deployment_id"]

    deployment = test_session.query(Deployment).filter(Deployment.id == deployment_id).one()
    assert deployment.kind == "logs"
    assert deployment.status == "queued"

    targets = (
        test_session.query(DeploymentTarget)
        .filter(DeploymentTarget.deployment_id == deployment_id)
        .all()
    )
    assert len(targets) == 1
    assert targets[0].agent_id == test_project.agent_id


def test_request_logs_is_rejected_while_a_task_is_pending(
    client, auth_headers, test_session, test_project
):
    test_session.add(
        Deployment(
            project_id=test_project.id,
            kind="deploy",
            status="queued",
            trigger_source="manual",
            queued_at=datetime.utcnow(),
        )
    )
    test_session.commit()

    response = client.post(f"/api/v1/projects/{test_project.id}/logs", headers=auth_headers)

    assert response.status_code == 409


def test_agent_snapshot_is_stored_and_listed(client, auth_headers, test_session, test_project):
    _bind_agent_token(test_session, test_project)

    ingest = client.post(
        "/api/v1/agents/diagnostics",
        headers=_agent_headers(),
        json={
            "deployment_id": None,
            "trigger": "manual",
            "reason": "requested from the panel",
            "content": "== docker compose ps ==\n[]\n== logs: api ==\nhello",
            "truncated": False,
        },
    )
    assert ingest.status_code == 201
    snapshot_id = ingest.json()["id"]

    listing = client.get(f"/api/v1/projects/{test_project.id}/logs", headers=auth_headers)
    assert listing.status_code == 200
    rows = listing.json()
    assert [row["id"] for row in rows] == [snapshot_id]
    assert rows[0]["trigger"] == "manual"

    detail = client.get(
        f"/api/v1/projects/{test_project.id}/logs/{snapshot_id}", headers=auth_headers
    )
    assert detail.status_code == 200
    assert "hello" in detail.json()["content"]


def test_oversized_content_is_capped(client, auth_headers, test_session, test_project):
    _bind_agent_token(test_session, test_project)

    ingest = client.post(
        "/api/v1/agents/diagnostics",
        headers=_agent_headers(),
        json={
            "trigger": "manual",
            "content": "x" * 200_000,
            "truncated": False,
        },
    )

    assert ingest.status_code == 201
    body = ingest.json()
    assert body["truncated"] is True
    assert body["byte_size"] <= 65536


def test_automatic_captures_are_deduplicated(client, auth_headers, test_session, test_project):
    _bind_agent_token(test_session, test_project)

    payload = {
        "trigger": "unhealthy",
        "reason": "health changed to unhealthy",
        "content": "boom",
        "truncated": False,
    }
    first = client.post("/api/v1/agents/diagnostics", headers=_agent_headers(), json=payload)
    second = client.post("/api/v1/agents/diagnostics", headers=_agent_headers(), json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.json().get("deduplicated") is True
