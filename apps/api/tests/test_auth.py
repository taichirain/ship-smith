import pytest
from fastapi.testclient import TestClient


class TestAuth:
    def test_login_success(self, client: TestClient, test_user):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "testpassword",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_password(self, client: TestClient, test_user):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "testuser",
                "password": "wrongpassword",
            },
        )
        assert response.status_code == 401

    def test_login_invalid_user(self, client: TestClient):
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent",
                "password": "testpassword",
            },
        )
        assert response.status_code == 401

    def test_protected_route_without_auth(self, client: TestClient):
        response = client.get("/api/v1/projects")
        assert response.status_code == 401

    def test_protected_route_with_auth(self, client: TestClient, auth_headers):
        response = client.get("/api/v1/projects", headers=auth_headers)
        assert response.status_code == 200
