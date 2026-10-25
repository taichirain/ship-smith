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
