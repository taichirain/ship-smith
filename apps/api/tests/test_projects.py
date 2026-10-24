import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from shipsmith_api.security import decrypt_secret


class TestProjects:
    def test_create_project(self, client: TestClient, auth_headers):
        response = client.post(
            "/api/v1/projects",
            headers=auth_headers,
            json={
                "name": "new-project",
                "git_repo": "https://github.com/test/new-repo.git",
                "git_branch": "develop",
                "git_credential_type": "http_token",
                "git_credential_username": "git",
                "git_credential_token": "secret-token",
                "deploy_workdir": "/opt/new-project",
                "compose_file": "docker-compose.yml",
                "compose_service": "app",
                "deploy_strategy": "compose-build",
                "healthcheck_url": "http://localhost:8080/health",
                "healthcheck_timeout_seconds": 10,
                "flags_file_path": "/opt/new-project/flags.json",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "new-project"
        assert data["git_branch"] == "develop"
        assert data["git_credential_type"] == "http_token"
        assert data["git_credential_configured"] is True
        assert data["git_credential_token"] is None
        assert "agent_id" in data
        assert "agent_token" in data
        assert len(data["agent_token"]) > 0

    def test_list_projects(self, client: TestClient, auth_headers, test_project):
        response = client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        project_names = [p["name"] for p in data]
        assert test_project.name in project_names

    def test_get_project(self, client: TestClient, auth_headers, test_project):
        response = client.get(
            f"/api/v1/projects/{test_project.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_project.id
        assert data["name"] == test_project.name
        assert "agent_id" in data

    def test_get_project_not_found(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/projects/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_update_project(self, client: TestClient, auth_headers, test_project):
        response = client.patch(
            f"/api/v1/projects/{test_project.id}",
            headers=auth_headers,
            json={
                "name": "updated-project",
                "git_branch": "feature-branch",
                "git_credential_type": "http_token",
                "git_credential_username": "git",
                "git_credential_token": "updated-token",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "updated-project"
        assert data["git_branch"] == "feature-branch"
        assert data["git_repo"] == test_project.git_repo
        assert data["git_credential_configured"] is True
        assert decrypt_secret(test_project.git_credential_token_encrypted) == "updated-token"

    @patch("shipsmith_api.routers.projects._is_git_available")
    @patch("shipsmith_api.routers.projects.subprocess.run")
    def test_list_git_branches_with_http_token(self, mock_run, mock_is_git_available, client: TestClient, auth_headers):
        mock_is_git_available.return_value = True

        heads_result = type("Result", (), {
            "returncode": 0,
            "stdout": "abc\trefs/heads/main\nbcd\trefs/heads/develop\n",
            "stderr": "",
        })()
        head_ref_result = type("Result", (), {
            "returncode": 0,
            "stdout": "ref: refs/heads/main\tHEAD\nabc\tHEAD\n",
            "stderr": "",
        })()
        mock_run.side_effect = [heads_result, head_ref_result]

        response = client.post(
            "/api/v1/projects/git-branches",
            headers=auth_headers,
            json={
                "git_repo": "https://github.com/test/private-repo.git",
                "git_credential_type": "http_token",
                "git_credential_username": "git",
                "git_credential_token": "secret-token",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["branches"][0]["name"] == "main"
        first_call = mock_run.call_args_list[0]
        assert "secret-token" in first_call.args[0][3]

    def test_update_project_empty_payload(self, client: TestClient, auth_headers, test_project):
        response = client.patch(
            f"/api/v1/projects/{test_project.id}",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 400

    def test_rotate_agent_token(self, client: TestClient, auth_headers, test_project):
        old_agent_id = test_project.agent_id
        response = client.post(
            f"/api/v1/projects/{test_project.id}/rotate-agent-token",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["agent_id"] == old_agent_id
        assert "agent_token" in data
        assert len(data["agent_token"]) > 0

    def test_get_project_status(self, client: TestClient, auth_headers, test_project):
        test_project.status.snapshot = {
            "runtime": {
                "os_name": "Linux",
                "shell": "/bin/bash",
                "docker_compose_command": "docker compose",
            },
            "app_health": {
                "status": "healthy",
            },
        }
        response = client.get(
            f"/api/v1/projects/{test_project.id}/status",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == test_project.id
        assert "health_status" in data
        assert "updated_at" in data
        assert data["runtime"]["os_name"] == "Linux"
        assert data["runtime"]["docker_compose_command"] == "docker compose"

    def test_generate_webhook_secret(self, client: TestClient, auth_headers, test_project):
        response = client.post(
            f"/api/v1/projects/{test_project.id}/generate-webhook-secret",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert "webhook_secret" in data
        assert len(data["webhook_secret"]) > 0
        assert "webhook_endpoint" in data

    def test_generate_deploy_commands_llm_not_configured(self, client: TestClient, auth_headers, test_project):
        response = client.post(
            f"/api/v1/projects/{test_project.id}/generate-deploy-commands",
            headers=auth_headers,
            json={},
        )
        assert response.status_code == 503

    @patch("shipsmith_api.routers.projects.get_settings")
    @patch("shipsmith_api.routers.projects.LLMClient.generate_deploy_commands")
    def test_generate_deploy_commands_success(self, mock_generate, mock_get_settings, client: TestClient, auth_headers, test_project):
        test_project.status.snapshot = {
            "runtime": {
                "os_name": "Linux",
                "os_release": "6.8",
                "shell": "/bin/bash",
                "docker_compose_command": "docker compose",
            },
            "containers": [],
            "app_health": {
                "status": "healthy",
            },
            "agent_version": "0.1.0",
        }

        mock_get_settings.return_value = type(
            "Settings",
            (),
            {
                "llm_enabled": True,
                "llm_provider": "openai",
                "llm_api_key": "test-key",
                "llm_api_base": "",
                "llm_model": "gpt-4o-mini",
                "llm_temperature": 0.3,
                "llm_timeout": 30,
            },
        )()
        mock_generate.return_value = {
            "plan": {
                "assumptions": ["已安装 Docker"],
                "prechecks": ["docker compose version"],
                "commands": [
                    {
                        "title": "更新代码",
                        "command": "git fetch --all --prune\n git checkout main\n git pull --ff-only",
                        "purpose": "同步最新代码",
                    }
                ],
                "verification": ["docker compose ps"],
                "explanation": "按 Linux + docker compose 生成。",
            },
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "llm_duration_ms": 1200,
        }

        response = client.post(
            f"/api/v1/projects/{test_project.id}/generate-deploy-commands",
            headers=auth_headers,
            json={"user_goal": "生成部署命令"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == test_project.id
        assert data["system_summary"]["os_name"] == "Linux"
        assert data["commands"][0]["title"] == "更新代码"
        assert "README.md" in data["source_files"]


class TestProjectListFilters:
    """Filters backing the dashboard drill-down cards."""

    @staticmethod
    def _create_project(session, name, health_status, agent_last_seen_at=None):
        from datetime import datetime
        from shipsmith_db import Project, ProjectStatus

        project = Project(
            name=name,
            git_repo=f"https://github.com/test/{name}.git",
            git_branch="main",
            git_credential_type="none",
            deploy_workdir=f"/opt/{name}",
            compose_file="docker-compose.yml",
            compose_service="app",
            deploy_strategy="compose-build",
            healthcheck_url=None,
            healthcheck_timeout_seconds=10,
            flags_file_path=f"/opt/{name}/flags.json",
            agent_id=f"agent-{name}",
            agent_token_hash="test-hash",
            webhook_endpoint_id=f"wh-{name}",
        )
        session.add(project)
        session.flush()
        if health_status is not None:
            session.add(
                ProjectStatus(
                    project_id=project.id,
                    health_status=health_status,
                    agent_last_seen_at=agent_last_seen_at or datetime.utcnow(),
                )
            )
        session.commit()
        return project

    def test_unknown_filter_includes_projects_without_status(
        self, client: TestClient, auth_headers, test_session
    ):
        self._create_project(test_session, "never-reported", None)

        response = client.get("/api/v1/projects?health_status=unknown", headers=auth_headers)

        assert response.status_code == 200
        assert {p["name"] for p in response.json()} == {"never-reported"}

    def test_offline_filter_uses_heartbeat_age(self, client: TestClient, auth_headers, test_session):
        from datetime import datetime, timedelta

        self._create_project(test_session, "just-recovered", "healthy", datetime.utcnow())
        self._create_project(
            test_session, "silent", "healthy", datetime.utcnow() - timedelta(days=1)
        )
        self._create_project(test_session, "never-reached-out", None)

        response = client.get("/api/v1/projects?health_status=offline", headers=auth_headers)

        assert response.status_code == 200
        assert {p["name"] for p in response.json()} == {"silent", "never-reached-out"}

    def test_stopped_filter_matches_intentional_stops(
        self, client: TestClient, auth_headers, test_session
    ):
        self._create_project(test_session, "parked", "stopped")
        self._create_project(test_session, "serving", "healthy")

        response = client.get("/api/v1/projects?health_status=stopped", headers=auth_headers)

        assert response.status_code == 200
        assert {p["name"] for p in response.json()} == {"parked"}

    def test_update_project_before_app_services_backfill(
        self, client: TestClient, auth_headers, test_session
    ):
        """Rows created before app_services existed can still be edited."""
        project = self._create_project(test_session, "legacy-row", "unknown")

        response = client.patch(
            f"/api/v1/projects/{project.id}",
            headers=auth_headers,
            json={"name": "legacy-row-renamed"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "legacy-row-renamed"
