import hashlib
from datetime import datetime

from shipsmith_db import Deployment, DeploymentTarget


def _payload(**overrides):
    payload = {
        "name": "migration-project",
        "git_repo": "https://github.com/test/repo.git",
        "git_branch": "main",
        "deploy_workdir": "/opt/migration-project",
        "compose_file": "docker-compose.yml",
        "compose_service": "api",
        "deploy_strategy": "compose-build",
        "healthcheck_url": "http://127.0.0.1:8080/ready",
        "healthcheck_timeout_seconds": 10,
        "healthcheck_expected_status": 200,
        "flags_file_path": "/opt/migration-project/flags.json",
        "migration_service": "api",
        "migration_command": "alembic upgrade head",
        "migration_timeout_seconds": 600,
        "migration_no_deps": True,
        "compose_profiles": ["data-sync"],
        "build_timeout_seconds": 5400,
        "pull_timeout_seconds": 1800,
        "build_no_cache": False,
    }
    payload.update(overrides)
    return payload


def test_create_project_with_migration_and_profiles(client, auth_headers):
    response = client.post("/api/v1/projects", headers=auth_headers, json=_payload())
    assert response.status_code == 201
    data = response.json()
    assert data["migration_service"] == "api"
    assert data["migration_command"] == "alembic upgrade head"
    assert data["compose_profiles"] == ["data-sync"]
    assert data["healthcheck_expected_status"] == 200
    assert data["build_timeout_seconds"] == 5400
    assert data["pull_timeout_seconds"] == 1800
    assert data["build_no_cache"] is False


def test_migration_command_requires_service(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json=_payload(migration_service="", migration_command="alembic upgrade head"),
    )
    assert response.status_code == 400


def test_invalid_compose_profile_is_rejected(client, auth_headers):
    response = client.post(
        "/api/v1/projects",
        headers=auth_headers,
        json=_payload(compose_profiles=["bad profile!"]),
    )
    assert response.status_code == 422


def test_update_migration_fields(client, auth_headers, test_project):
    response = client.patch(
        f"/api/v1/projects/{test_project.id}",
        headers=auth_headers,
        json={
            "migration_service": "api",
            "migration_command": "alembic upgrade head",
            "migration_no_deps": False,
            "compose_profiles": ["sync"],
            "healthcheck_expected_status": 204,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["migration_command"] == "alembic upgrade head"
    assert data["migration_no_deps"] is False
    assert data["compose_profiles"] == ["sync"]
    assert data["healthcheck_expected_status"] == 204


def test_agent_task_includes_migration_fields(client, test_session, test_project):
    test_project.agent_token_hash = hashlib.sha256(b"agent-token").hexdigest()
    test_project.migration_service = "api"
    test_project.migration_command = "alembic upgrade head"
    test_project.migration_timeout_seconds = 900
    test_project.migration_no_deps = False
    test_project.compose_profiles = ["data-sync"]
    test_project.healthcheck_expected_status = 204
    test_session.commit()

    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="queued",
        trigger_source="manual",
        queued_at=datetime.utcnow(),
    )
    test_session.add(deployment)
    test_session.flush()
    test_session.add(
        DeploymentTarget(
            deployment_id=deployment.id,
            agent_id=test_project.agent_id,
            status="queued",
        )
    )
    test_session.commit()

    response = client.get(
        "/api/v1/agents/tasks",
        headers={"Authorization": "Bearer agent-token"},
    )
    assert response.status_code == 200
    task = response.json()["task"]
    assert task["migration_service"] == "api"
    assert task["migration_command"] == "alembic upgrade head"
    assert task["migration_timeout_seconds"] == 900
    assert task["migration_no_deps"] is False
    assert task["compose_profiles"] == ["data-sync"]
    assert task["healthcheck_expected_status"] == 204


def test_update_migration_fields_accepts_null_defaults(client, auth_headers, test_project):
    response = client.patch(
        f"/api/v1/projects/{test_project.id}",
        headers=auth_headers,
        json={
            "migration_service": None,
            "compose_profiles": None,
            "migration_no_deps": None,
            "migration_timeout_seconds": None,
            "healthcheck_expected_status": None,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["migration_service"] == ""
    assert data["compose_profiles"] == []
    assert data["migration_no_deps"] is True
    assert data["migration_timeout_seconds"] == 600
    assert data["healthcheck_expected_status"] == 200


def test_agent_task_includes_build_tuning(client, test_session, test_project):
    test_project.agent_token_hash = hashlib.sha256(b"agent-token").hexdigest()
    test_project.build_timeout_seconds = 7200
    test_project.pull_timeout_seconds = 2400
    test_project.build_no_cache = True
    test_session.commit()

    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="queued",
        trigger_source="manual",
        queued_at=datetime.utcnow(),
    )
    test_session.add(deployment)
    test_session.flush()
    test_session.add(
        DeploymentTarget(
            deployment_id=deployment.id,
            agent_id=test_project.agent_id,
            status="queued",
        )
    )
    test_session.commit()

    response = client.get(
        "/api/v1/agents/tasks",
        headers={"Authorization": "Bearer agent-token"},
    )
    assert response.status_code == 200
    task = response.json()["task"]
    assert task["build_timeout_seconds"] == 7200
    assert task["pull_timeout_seconds"] == 2400
    assert task["build_no_cache"] is True
