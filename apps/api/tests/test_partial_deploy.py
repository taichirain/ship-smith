from shipsmith_db import Deployment


def _register_services(test_session, test_project, services):
    test_project.app_services = services
    test_session.commit()


def test_deploy_a_subset_of_services(client, auth_headers, test_session, test_project):
    _register_services(test_session, test_project, ["app", "web"])

    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={"services": ["web"]},
    )

    assert response.status_code == 201
    deployment = (
        test_session.query(Deployment)
        .filter(Deployment.id == response.json()["id"])
        .one()
    )
    assert deployment.requested_services == ["web"]


def test_deploy_without_services_leaves_the_field_empty(
    client, auth_headers, test_session, test_project
):
    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 201
    deployment = (
        test_session.query(Deployment)
        .filter(Deployment.id == response.json()["id"])
        .one()
    )
    assert deployment.requested_services is None


def test_deploy_rejects_service_outside_app_services(
    client, auth_headers, test_session, test_project
):
    _register_services(test_session, test_project, ["app", "web"])

    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={"services": ["database"]},
    )

    assert response.status_code == 400


def test_deploy_rejects_duplicate_services(client, auth_headers, test_session, test_project):
    _register_services(test_session, test_project, ["app", "web"])

    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={"services": ["web", "web"]},
    )

    assert response.status_code == 400


def test_release_tag_env_round_trips(client, auth_headers, test_session, test_project):
    test_project.release_tag_env = ""
    test_session.commit()

    response = client.patch(
        f"/api/v1/projects/{test_project.id}",
        headers=auth_headers,
        json={"release_tag_env": "ALPHA_RELEASE_TAG"},
    )

    assert response.status_code == 200, response.text
    assert response.json()["release_tag_env"] == "ALPHA_RELEASE_TAG"
    test_session.refresh(test_project)
    assert test_project.release_tag_env == "ALPHA_RELEASE_TAG"


def test_full_deploy_snapshots_the_app_services(client, auth_headers, test_session, test_project):
    test_project.app_services = ["app", "web"]
    test_project.service_scope = "app"
    test_session.commit()

    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["effective_services"] == ["app", "web"]
    assert body["effective_service_scope"] == "app"


def test_partial_deploy_snapshots_only_the_requested_services(
    client, auth_headers, test_session, test_project
):
    test_project.app_services = ["app", "web"]
    test_project.service_scope = "app"
    test_session.commit()

    response = client.post(
        f"/api/v1/projects/{test_project.id}/deploy",
        headers=auth_headers,
        json={"services": ["web"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["effective_services"] == ["web"]
    assert body["requested_services"] == ["web"]


def test_rollback_replays_the_snapshot_not_the_current_config(
    client, auth_headers, test_session, test_project
):
    from datetime import datetime

    target = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="success",
        trigger_source="manual",
        commit_hash="abc123",
        queued_at=datetime.utcnow(),
        finished_at=datetime.utcnow(),
        effective_services=["legacy-web"],
        effective_service_scope="app",
    )
    test_session.add(target)
    test_session.commit()
    test_session.refresh(target)

    # the project config has since changed
    test_project.app_services = ["app", "new-web"]
    test_session.commit()

    response = client.post(
        f"/api/v1/projects/{test_project.id}/rollback",
        headers=auth_headers,
        json={"target_deployment_id": target.id},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["effective_services"] == ["legacy-web"]
    assert body["requested_services"] == ["legacy-web"]
    assert body["effective_service_scope"] == "app"
