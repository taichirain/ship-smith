import pytest
from fastapi.testclient import TestClient


class TestDeployments:
    def test_create_manual_deployment(self, client: TestClient, auth_headers, test_project):
        response = client.post(
            f"/api/v1/projects/{test_project.id}/deploy",
            headers=auth_headers,
            json={
                "commit_hash": "abc123def456",
                "trigger_source": "manual",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["project_id"] == test_project.id
        assert data["kind"] == "deploy"
        assert data["status"] == "queued"
        assert data["trigger_source"] == "manual"
        assert data["commit_hash"] == "abc123def456"

    def test_create_deployment_conflict(self, client: TestClient, auth_headers, test_project):
        client.post(
            f"/api/v1/projects/{test_project.id}/deploy",
            headers=auth_headers,
            json={
                "commit_hash": "abc123",
                "trigger_source": "manual",
            },
        )
        response = client.post(
            f"/api/v1/projects/{test_project.id}/deploy",
            headers=auth_headers,
            json={
                "commit_hash": "def456",
                "trigger_source": "manual",
            },
        )
        assert response.status_code == 409

    def test_list_deployments(self, client: TestClient, auth_headers, test_project, test_deployment):
        response = client.get(
            f"/api/v1/projects/{test_project.id}/deployments",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_deployment(self, client: TestClient, auth_headers, test_deployment):
        response = client.get(
            f"/api/v1/deployments/{test_deployment.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_deployment.id
        assert data["kind"] == "deploy"

    def test_get_deployment_not_found(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/deployments/99999", headers=auth_headers)
        assert response.status_code == 404

    def test_rollback_deployment(self, client: TestClient, auth_headers, test_project, test_deployment):
        response = client.post(
            f"/api/v1/projects/{test_project.id}/rollback",
            headers=auth_headers,
            json={
                "target_deployment_id": test_deployment.id,
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["kind"] == "rollback"
        assert data["status"] == "queued"
        assert data["target_deployment_id"] == test_deployment.id

    def test_get_deployment_detail(self, client: TestClient, auth_headers, test_deployment):
        response = client.get(
            f"/api/v1/deployments/{test_deployment.id}/detail",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_deployment.id

    def test_get_deployment_logs(self, client: TestClient, auth_headers, test_deployment):
        response = client.get(
            f"/api/v1/deployments/{test_deployment.id}/logs",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
