import logging
import time
from typing import Optional, Dict, Any

import httpx

from .config import AgentSettings


logger = logging.getLogger(__name__)


class CoreClient:
    def __init__(self, settings: AgentSettings):
        self.settings = settings
        self.base_url = settings.core_url.rstrip("/")
        self.token = settings.agent_token
        self._client: Optional[httpx.Client] = None

    def _get_client(self) -> httpx.Client:
        if self._client is None:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            }
            self._client = httpx.Client(
                headers=headers,
                timeout=30.0,
            )
        return self._client

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def poll_task(self) -> Optional[Dict[str, Any]]:
        try:
            client = self._get_client()
            response = client.get(f"{self.base_url}/agents/tasks")
            response.raise_for_status()
            data = response.json()
            return data.get("task")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error("Agent token is invalid or expired")
            else:
                logger.error(f"Failed to poll tasks: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Failed to poll tasks: {e}")
            return None

    def start_task(self, task_id: int) -> bool:
        try:
            client = self._get_client()
            response = client.post(
                f"{self.base_url}/agents/tasks/{task_id}/start",
                json={},
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to start task {task_id}: {e}")
            return False

    def send_logs(self, task_id: int, seq: int, phase: str, content: str) -> bool:
        try:
            client = self._get_client()
            response = client.post(
                f"{self.base_url}/agents/tasks/{task_id}/logs",
                json={
                    "seq": seq,
                    "phase": phase,
                    "content": content,
                },
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to send logs for task {task_id} (seq {seq}): {e}")
            return False

    def send_task_heartbeat(self, task_id: int) -> bool:
        try:
            client = self._get_client()
            response = client.post(
                f"{self.base_url}/agents/tasks/{task_id}/heartbeat",
                json={},
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to send task heartbeat for task {task_id}: {e}")
            return False

    def finish_task(
        self,
        task_id: int,
        status: str,
        commit_hash: Optional[str] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        failure_phase: Optional[str] = None,
        target_commit_hash: Optional[str] = None,
        previous_commit_hash: Optional[str] = None,
        image_snapshot: Optional[Dict[str, Any]] = None,
        health_result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            client = self._get_client()
            payload = {
                "status": status,
                "commit_hash": commit_hash,
                "error_code": error_code,
                "error_message": error_message,
            }
            if failure_phase:
                payload["failure_phase"] = failure_phase
            if target_commit_hash:
                payload["target_commit_hash"] = target_commit_hash
            if previous_commit_hash:
                payload["previous_commit_hash"] = previous_commit_hash
            if image_snapshot is not None:
                payload["image_snapshot"] = image_snapshot
            if health_result is not None:
                payload["health_result"] = health_result
            response = client.post(
                f"{self.base_url}/agents/tasks/{task_id}/finish",
                json=payload,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to finish task {task_id}: {e}")
            return False

    def send_heartbeat(self, payload: Dict[str, Any]) -> bool:
        try:
            client = self._get_client()
            response = client.post(
                f"{self.base_url}/agents/heartbeat",
                json=payload,
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.warning(f"Failed to send heartbeat: {e}")
            return False

    def sync_flags(self, current_version: int) -> Optional[Dict[str, Any]]:
        try:
            client = self._get_client()
            response = client.get(
                f"{self.base_url}/agents/flags/sync",
                params={"current_version": current_version},
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"Failed to sync flags: {e}")
            return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
