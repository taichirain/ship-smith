import hashlib
from datetime import datetime, timedelta

from shipsmith_api.alerts import create_or_update_alert
from shipsmith_api.monitor import scan_offline_projects
from shipsmith_db import Alert


def _bind_agent_token(test_session, test_project, token="agent-token"):
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    test_session.commit()


def test_offline_alert_created_and_recovered(test_session, test_project):
    status = test_project.status
    old = datetime.utcnow() - timedelta(seconds=1200)
    status.agent_last_seen_at = old
    status.health_status = "healthy"
    test_session.commit()

    first = scan_offline_projects(test_session, threshold_seconds=600)
    assert first["offline"] == 1

    open_alert = (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "agent_offline",
            Alert.status == "open",
        )
        .first()
    )
    assert open_alert is not None

    second = scan_offline_projects(test_session, threshold_seconds=600)
    assert second["offline"] == 1
    assert (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "agent_offline",
            Alert.status == "open",
        )
        .count()
        == 1
    )

    status.agent_last_seen_at = datetime.utcnow()
    test_session.commit()

    recovered = scan_offline_projects(test_session, threshold_seconds=600)
    assert recovered["recovered"] == 1
    test_session.refresh(open_alert)
    assert open_alert.status == "resolved"


def test_heartbeat_recovers_offline_alert(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    status = test_project.status
    old = datetime.utcnow() - timedelta(seconds=1200)
    status.agent_last_seen_at = old
    status.snapshot = {"_detected_offline_at": old.isoformat()}
    test_session.commit()

    create_or_update_alert(
        test_session,
        test_project.id,
        "agent_offline",
        {"agent_id": test_project.agent_id},
    )

    response = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": "Bearer agent-token"},
        json={"app_health": {"status": "healthy"}},
    )
    assert response.status_code == 200

    alert = (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "agent_offline",
        )
        .order_by(Alert.id.desc())
        .first()
    )
    assert alert.status == "resolved"
    test_session.refresh(status)
    assert "_detected_offline_at" not in (status.snapshot or {})


def test_agent_config_endpoint(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)

    response = client.get(
        "/api/v1/agents/config",
        headers={"Authorization": "Bearer agent-token"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["project_id"] == test_project.id
    assert data["healthcheck_url"] == test_project.healthcheck_url
    assert data["healthcheck_timeout_seconds"] == test_project.healthcheck_timeout_seconds
    assert data["healthcheck_expected_status"] == test_project.healthcheck_expected_status
    assert data["deploy_workdir"] == test_project.deploy_workdir
    assert data["compose_file"] == test_project.compose_file
    assert data["compose_profiles"] == (test_project.compose_profiles or [])


def test_heartbeat_resolves_stale_health_alert(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    status = test_project.status
    status.health_status = "unknown"
    test_session.commit()

    create_or_update_alert(
        test_session,
        test_project.id,
        "health_unhealthy",
        {"agent_id": test_project.agent_id},
    )

    response = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": "Bearer agent-token"},
        json={"app_health": {"status": "healthy"}},
    )
    assert response.status_code == 200

    alert = (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "health_unhealthy",
        )
        .order_by(Alert.id.desc())
        .first()
    )
    assert alert.status == "resolved"
    test_session.refresh(status)
    assert status.health_status == "healthy"


def test_health_alert_created_then_recovered(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    status = test_project.status
    status.health_status = "healthy"
    test_session.commit()

    first = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": "Bearer agent-token"},
        json={"app_health": {"status": "unhealthy"}},
    )
    assert first.status_code == 200

    alert = (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "health_unhealthy",
            Alert.status == "open",
        )
        .first()
    )
    assert alert is not None

    second = client.post(
        "/api/v1/agents/heartbeat",
        headers={"Authorization": "Bearer agent-token"},
        json={"app_health": {"status": "healthy"}},
    )
    assert second.status_code == 200

    test_session.refresh(alert)
    assert alert.status == "resolved"
    test_session.refresh(status)
    assert status.health_status == "healthy"


def test_repeated_health_cycles_keep_history(client, test_session, test_project):
    _bind_agent_token(test_session, test_project)
    status = test_project.status
    status.health_status = "healthy"
    test_session.commit()

    headers = {"Authorization": "Bearer agent-token"}
    for _ in range(2):
        unhealthy = client.post(
            "/api/v1/agents/heartbeat",
            headers=headers,
            json={"app_health": {"status": "unhealthy"}},
        )
        assert unhealthy.status_code == 200
        healthy = client.post(
            "/api/v1/agents/heartbeat",
            headers=headers,
            json={"app_health": {"status": "healthy"}},
        )
        assert healthy.status_code == 200

    alerts = (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "health_unhealthy",
        )
        .order_by(Alert.id.asc())
        .all()
    )
    assert len(alerts) == 2
    assert all(alert.status == "resolved" for alert in alerts)
    assert (
        test_session.query(Alert)
        .filter(
            Alert.project_id == test_project.id,
            Alert.alert_type == "health_unhealthy",
            Alert.status.in_(["open", "acknowledged"]),
        )
        .count()
        == 0
    )
