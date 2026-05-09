import pytest
from fastapi.testclient import TestClient


class TestFeatureFlags:
    def test_list_flags(self, client: TestClient, auth_headers, test_project, test_feature_flag):
        response = client.get(
            f"/api/v1/projects/{test_project.id}/flags",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        flag_keys = [f["key"] for f in data]
        assert "test_feature" in flag_keys

    def test_create_flag(self, client: TestClient, auth_headers, test_project):
        response = client.post(
            f"/api/v1/projects/{test_project.id}/flags",
            headers=auth_headers,
            json={
                "key": "new_feature",
                "enabled": True,
                "description": "A new feature flag",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["key"] == "new_feature"
        assert data["enabled"] is True
        assert data["description"] == "A new feature flag"
        assert data["version"] == 1

    def test_update_flag(self, client: TestClient, auth_headers, test_feature_flag):
        response = client.patch(
            f"/api/v1/flags/{test_feature_flag.id}",
            headers=auth_headers,
            json={
                "enabled": False,
                "description": "Updated description",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["description"] == "Updated description"
        assert data["version"] == 2

    def test_archive_flag(self, client: TestClient, auth_headers, test_feature_flag):
        response = client.post(
            f"/api/v1/flags/{test_feature_flag.id}/archive",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["flag_id"] == test_feature_flag.id
        assert data["archived"] is True

    def test_unarchive_flag(self, client: TestClient, auth_headers, test_session, test_project, test_user):
        from shipsmith_db import FeatureFlag

        archived_flag = FeatureFlag(
            project_id=test_project.id,
            key="archived_flag",
            enabled=False,
            archived=True,
            version=2,
            updated_by="testuser",
        )
        test_session.add(archived_flag)
        test_session.commit()
        test_session.refresh(archived_flag)

        response = client.post(
            f"/api/v1/flags/{archived_flag.id}/unarchive",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["flag_id"] == archived_flag.id
        assert data["archived"] is False

    def test_delete_flag(self, client: TestClient, auth_headers, test_feature_flag):
        response = client.delete(
            f"/api/v1/flags/{test_feature_flag.id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ok"] is True
        assert data["flag_id"] == test_feature_flag.id
        assert data["deleted"] is True

    def test_get_flags_snapshot(self, client: TestClient, auth_headers, test_project, test_feature_flag):
        response = client.get(
            f"/api/v1/projects/{test_project.id}/flags/snapshot",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["project_id"] == test_project.id
        assert "version" in data
        assert "flags" in data
        assert isinstance(data["flags"], dict)

    def test_list_flags_include_archived(self, client: TestClient, auth_headers, test_session, test_project):
        from shipsmith_db import FeatureFlag

        normal_flag = FeatureFlag(
            project_id=test_project.id,
            key="normal_flag",
            enabled=True,
            archived=False,
            version=1,
            updated_by="testuser",
        )
        archived_flag = FeatureFlag(
            project_id=test_project.id,
            key="archived_flag",
            enabled=False,
            archived=True,
            version=1,
            updated_by="testuser",
        )
        test_session.add(normal_flag)
        test_session.add(archived_flag)
        test_session.commit()

        response_default = client.get(
            f"/api/v1/projects/{test_project.id}/flags",
            headers=auth_headers,
        )
        default_flags = response_default.json()
        default_keys = [f["key"] for f in default_flags]
        assert "normal_flag" in default_keys
        assert "archived_flag" not in default_keys

        response_with_archived = client.get(
            f"/api/v1/projects/{test_project.id}/flags?include_archived=true",
            headers=auth_headers,
        )
        all_flags = response_with_archived.json()
        all_keys = [f["key"] for f in all_flags]
        assert "normal_flag" in all_keys
        assert "archived_flag" in all_keys
