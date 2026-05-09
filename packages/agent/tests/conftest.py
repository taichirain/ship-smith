import os
import sys
import pytest
from unittest.mock import patch, MagicMock


sys.path.insert(
    0,
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)


@pytest.fixture
def mock_settings():
    with patch("shipsmith_agent.config.get_settings") as mock_get:
        settings = MagicMock()
        settings.core_url = "http://localhost:8000/api/v1"
        settings.agent_token = "test-token-123"
        settings.workdir = "/opt/test"
        settings.poll_interval_seconds = 30
        settings.heartbeat_interval_seconds = 30
        settings.flags_sync_interval_seconds = 30
        settings.log_level = "INFO"
        mock_get.return_value = settings
        yield settings


@pytest.fixture
def mock_httpx_client():
    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__ = MagicMock(return_value=mock_client)
        mock_client_cls.return_value.__exit__ = MagicMock(return_value=False)
        yield mock_client
