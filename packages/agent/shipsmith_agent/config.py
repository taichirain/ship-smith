import os
from functools import lru_cache
from typing import Optional

from pydantic import BaseModel


class AgentSettings(BaseModel):
    core_url: str
    agent_token: str
    workdir: Optional[str] = None
    config_file: Optional[str] = None

    poll_interval_seconds: int = 30
    heartbeat_interval_seconds: int = 30
    flags_sync_interval_seconds: int = 30

    log_level: str = "INFO"


def _load_env_from_file() -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value


@lru_cache
def get_settings() -> AgentSettings:
    _load_env_from_file()

    return AgentSettings(
        core_url=os.environ.get("SHIPSMITH_CORE_URL", "http://localhost:8000/api/v1"),
        agent_token=os.environ.get("SHIPSMITH_AGENT_TOKEN", ""),
        workdir=os.environ.get("SHIPSMITH_WORKDIR"),
        config_file=os.environ.get("SHIPSMITH_CONFIG_FILE"),
        poll_interval_seconds=int(os.environ.get("SHIPSMITH_POLL_INTERVAL", "30")),
        heartbeat_interval_seconds=int(os.environ.get("SHIPSMITH_HEARTBEAT_INTERVAL", "30")),
        flags_sync_interval_seconds=int(os.environ.get("SHIPSMITH_FLAGS_INTERVAL", "30")),
        log_level=os.environ.get("SHIPSMITH_LOG_LEVEL", "INFO"),
    )
