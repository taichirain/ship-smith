from shipsmith_api.alerts import create_or_update_alert, resolve_alert_by_fingerprint


def test_create_and_resolve_alert(test_session, test_project):
    alert = create_or_update_alert(
        test_session,
        test_project.id,
        "agent_offline",
        {"agent_id": "agent-test-123", "offline_threshold_minutes": 10},
    )
    assert alert is not None
    assert alert.alert_metadata["agent_id"] == "agent-test-123"
    assert alert.status == "open"

    resolve_alert_by_fingerprint(
        test_session,
        test_project.id,
        "agent_offline",
        {"agent_id": "agent-test-123"},
    )
    test_session.refresh(alert)
    assert alert.status == "resolved"
