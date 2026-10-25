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
