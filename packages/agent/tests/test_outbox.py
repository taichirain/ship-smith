from shipsmith_agent.main import Agent
from shipsmith_agent.outbox import Outbox


class FakeClient:
    def __init__(self, ok=False):
        self.ok = ok
        self.finished = []
        self.logs = []

    def finish_task(self, task_id, **payload):
        self.finished.append((task_id, payload))
        return self.ok

    def send_logs(self, task_id, seq, phase, content):
        self.logs.append((task_id, seq, phase, content))
        return self.ok


def make_agent(tmp_path, ok=False):
    agent = Agent.__new__(Agent)
    agent.outbox = Outbox("/tmp/work", state_dir=str(tmp_path))
    agent.client = FakeClient(ok=ok)
    return agent


def test_outbox_roundtrip(tmp_path):
    outbox = Outbox("/tmp/work", state_dir=str(tmp_path))
    outbox.enqueue_result(7, {"status": "success"})
    outbox.enqueue_log(7, 0, "git_fetch", "line")

    results = outbox.pending_results()
    logs = outbox.pending_logs()
    assert len(results) == 1
    assert results[0][1]["task_id"] == 7
    assert results[0][1]["payload"]["status"] == "success"
    assert len(logs) == 1
    assert logs[0][1]["content"] == "line"

    outbox.remove(results[0][0])
    outbox.remove(logs[0][0])
    assert outbox.pending_results() == []
    assert outbox.pending_logs() == []


def test_finish_failure_is_queued_then_flushed(tmp_path):
    agent = make_agent(tmp_path, ok=False)
    assert agent._finish_task(7, status="success", commit_hash="abc") is False
    assert len(agent.outbox.pending_results()) == 1

    agent.client.ok = True
    agent._flush_outbox()
    assert agent.outbox.pending_results() == []
    assert agent.client.finished[-1][0] == 7
    assert agent.client.finished[-1][1]["commit_hash"] == "abc"


def test_log_failure_is_queued_then_flushed(tmp_path):
    agent = make_agent(tmp_path, ok=False)
    assert agent._send_logs(7, 0, "git_fetch", "line") is False
    assert len(agent.outbox.pending_logs()) == 1

    agent.client.ok = True
    agent._flush_outbox()
    assert agent.outbox.pending_logs() == []
    assert agent.client.logs[-1] == (7, 0, "git_fetch", "line")
