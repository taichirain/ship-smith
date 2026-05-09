import pytest
import hmac
import hashlib
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


class TestWebhooks:
    def test_github_webhook_valid_signature(self, client: TestClient, test_session, test_project):
        import secrets

        secret = secrets.token_hex(16)
        test_project.webhook_secret = secret
        test_session.commit()

        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'
        
        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-123",
            },
        )
        assert response.status_code in [200, 202]

    def test_github_webhook_invalid_signature(self, client: TestClient, test_project):
        import secrets

        secret = secrets.token_hex(16)
        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'

        wrong_signature = hmac.new(
            b"wrong_secret",
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={wrong_signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-456",
            },
        )
        assert response.status_code == 401

    def test_github_webhook_no_signature(self, client: TestClient, test_project):
        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-789",
            },
        )
        assert response.status_code == 401

    def test_github_webhook_wrong_branch(self, client: TestClient, test_session, test_project):
        import secrets

        secret = secrets.token_hex(16)
        test_project.webhook_secret = secret
        test_project.git_branch = "main"
        test_session.commit()

        payload = '{"ref": "refs/heads/develop", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'

        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-delivery-wrong-branch",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ignored"] is True

    def test_github_webhook_idempotency(self, client: TestClient, test_session, test_project):
        import secrets

        secret = secrets.token_hex(16)
        test_project.webhook_secret = secret
        test_session.commit()

        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'

        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        delivery_id = "test-delivery-idempotent-123"

        response1 = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": delivery_id,
            },
        )

        response2 = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": delivery_id,
            },
        )

        assert response2.status_code == 200
        data = response2.json()
        assert data["duplicate"] is True

    def test_gitlab_webhook_valid_token(self, client: TestClient, test_session, test_project):
        import secrets

        secret = secrets.token_hex(16)
        test_project.webhook_secret = secret
        test_session.commit()

        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "project": {"path_with_namespace": "test/repo"}}'

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/gitlab",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Gitlab-Token": secret,
                "X-Gitlab-Event": "Push Hook",
            },
        )
        assert response.status_code in [200, 202]

    def test_gitlab_webhook_invalid_token(self, client: TestClient, test_project):
        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "project": {"path_with_namespace": "test/repo"}}'

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/gitlab",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Gitlab-Token": "wrong_secret",
                "X-Gitlab-Event": "Push Hook",
            },
        )
        assert response.status_code == 401

    def test_github_webhook_no_secret_configured(self, client: TestClient, test_session, test_project):
        test_project.webhook_secret = None
        test_session.commit()

        payload = '{"ref": "refs/heads/main", "commits": [{"id": "abc123"}], "repository": {"full_name": "test/repo"}}'

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-GitHub-Event": "push",
                "X-GitHub-Delivery": "test-no-secret-123",
            },
        )
        assert response.status_code == 400

    def test_webhook_endpoint_not_found(self, client: TestClient):
        response = client.post(
            "/api/v1/webhooks/non-existent-endpoint/github",
            json={"ref": "refs/heads/main"},
        )
        assert response.status_code == 404

    def test_github_webhook_non_push_event(self, client: TestClient, test_session, test_project):
        import secrets

        secret = secrets.token_hex(16)
        test_project.webhook_secret = secret
        test_session.commit()

        payload = '{"action": "opened", "number": 1}'

        signature = hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        response = client.post(
            f"/api/v1/webhooks/{test_project.webhook_endpoint_id}/github",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Hub-Signature-256": f"sha256={signature}",
                "X-GitHub-Event": "pull_request",
                "X-GitHub-Delivery": "test-pr-event",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["ignored"] is True
