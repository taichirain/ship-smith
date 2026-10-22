import hashlib
from datetime import datetime

import httpx

from shipsmith_agent.client import CoreClient
from shipsmith_agent.main import Agent
from shipsmith_agent.outbox import Outbox
from shipsmith_db import Deployment, DeploymentLog, DeploymentTarget


class ToggleCoreTransport:
    def __init__(self, test_client, token: str):
        self.test_client = test_client
        self.token = token
        self.online = False

    def post(self, url, json):
        if not self.online:
            raise httpx.ConnectError("simulated Core outage")
        path = url.removeprefix("http://core.test")
        return self.test_client.post(path, headers={"Authorization": f"Bearer {self.token}"}, json=json)


def test_agent_replays_result_and_logs_after_core_reconnect(
    client, test_session, test_project, tmp_path
):
    token = "outbox-test-token"
    test_project.agent_token_hash = hashlib.sha256(token.encode()).hexdigest()
    deployment = Deployment(
        project_id=test_project.id,
        kind="deploy",
        status="running",
        trigger_source="manual",
        commit_hash="abc123",
        queued_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
    )
    test_session.add(deployment)
    test_session.flush()
    target = DeploymentTarget(
        deployment_id=deployment.id,
        agent_id=test_project.agent_id,
        status="running",
    )
    test_session.add(target)
    test_session.commit()

    transport = ToggleCoreTransport(client, token)
    core_client = CoreClient.__new__(CoreClient)
    core_client.base_url = "http://core.test/api/v1"
    core_client.token = token
    core_client._client = transport

    agent = Agent.__new__(Agent)
    agent.client = core_client
    agent.outbox = Outbox(str(tmp_path / "work"), state_dir=str(tmp_path))

    assert agent._send_logs(deployment.id, 0, "migration", "migration complete") is False
    assert agent._finish_task(deployment.id, status="success", commit_hash="abc123") is False
    assert len(agent.outbox.pending_logs()) == 1
    assert len(agent.outbox.pending_results()) == 1
    test_session.refresh(deployment)
    assert deployment.status == "running"

    transport.online = True
    agent._flush_outbox()

    test_session.refresh(deployment)
    assert deployment.status == "success"
    assert agent.outbox.pending_logs() == []
    assert agent.outbox.pending_results() == []
    logs = test_session.query(DeploymentLog).filter_by(deployment_id=deployment.id).all()
    assert len(logs) == 1
    assert logs[0].content == "migration complete"
