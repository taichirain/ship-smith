"""Shared Agent liveness rules.

One source of truth for "is this Agent still reporting?" so the dashboard
summary and the project list filters never disagree about the offline count.
"""

from datetime import datetime, timedelta
from typing import Optional

from .config import get_settings


def is_agent_offline(agent_last_seen_at: Optional[datetime]) -> bool:
    """Return True when a project has no Agent heartbeat or one that is too old."""
    if not agent_last_seen_at:
        return True
    threshold = timedelta(seconds=get_settings().agent_offline_threshold_seconds)
    return (datetime.utcnow() - agent_last_seen_at) > threshold
