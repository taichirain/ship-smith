import json
import hashlib
import asyncio
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from .config import get_settings


DEFAULT_TIMEOUT = 10
ERROR_EVENT_TYPES = {"agent_offline", "health_degraded", "health_unhealthy", "deployment_failed"}
RECOVERY_EVENT_TYPES = {"agent_recovered", "health_recovered", "deployment_success"}


def _build_fingerprint(project_id: int, event_type: str, event_details: Dict[str, Any]) -> str:
    fingerprint_parts = [str(project_id), event_type]

    if event_details.get("commit_hash"):
        fingerprint_parts.append(event_details["commit_hash"])
    if event_details.get("error_code"):
        fingerprint_parts.append(event_details["error_code"])
    if event_details.get("agent_id"):
        fingerprint_parts.append(event_details["agent_id"])
    if event_details.get("message"):
        fingerprint_parts.append(event_details["message"][:100])

    fingerprint_raw = "|".join(fingerprint_parts)
    return hashlib.sha256(fingerprint_raw.encode("utf-8")).hexdigest()[:32]


def _is_error_event(event_type: str) -> bool:
    return event_type in ERROR_EVENT_TYPES


def _is_recovery_event(event_type: str) -> bool:
    return event_type in RECOVERY_EVENT_TYPES


def _get_last_unsuppressed_delivery(
    db: Session,
    project_id: int,
    channel_id: int,
    event_type: str,
    fingerprint: Optional[str],
) -> Optional[Any]:
    from shipsmith_db import NotificationDelivery

    query = (
        db.query(NotificationDelivery)
        .filter(
            NotificationDelivery.project_id == project_id,
            NotificationDelivery.channel_id == channel_id,
            NotificationDelivery.event_type == event_type,
            NotificationDelivery.is_suppressed == False,
        )
        .order_by(NotificationDelivery.created_at.desc())
    )

    if fingerprint:
        query = query.filter(NotificationDelivery.fingerprint == fingerprint)

    return query.first()


def _should_suppress(
    db: Session,
    project_id: int,
    channel_id: int,
    event_type: str,
    fingerprint: Optional[str],
    cooldown_seconds: int,
    send_recovery: bool,
    is_recovery: bool,
) -> bool:
    if cooldown_seconds <= 0:
        return False

    if is_recovery:
        return False

    if not _is_error_event(event_type):
        return False

    last_delivery = _get_last_unsuppressed_delivery(
        db, project_id, channel_id, event_type, fingerprint
    )

    if not last_delivery:
        return False

    cooldown_window = timedelta(seconds=cooldown_seconds)
    time_since_last = datetime.utcnow() - (last_delivery.sent_at or last_delivery.created_at)

    return time_since_last < cooldown_window


def _send_http_request(url: str, method: str = "POST", headers: Dict[str, str] = None, data: Dict[str, Any] = None, timeout: int = DEFAULT_TIMEOUT) -> Tuple[bool, Optional[int], str]:
    headers = headers or {}
    req_data = None

    if data is not None:
        req_data = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = headers.get("Content-Type", "application/json")

    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return True, response.status, response.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return False, e.code, e.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return False, None, str(e)


def _build_generic_webhook_payload(channel_type: str, event_type: str, project_name: str, event_details: Dict[str, Any]) -> Dict[str, Any]:
    status_emoji = {
        "deployment_success": "✅",
        "deployment_failed": "❌",
        "agent_offline": "⚠️",
        "health_degraded": "⚠️",
        "health_unhealthy": "🔴",
        "health_recovered": "💚",
        "agent_recovered": "💚",
        "test": "🧪",
    }

    return {
        "event_type": event_type,
        "project_name": project_name,
        "emoji": status_emoji.get(event_type, "📢"),
        "occurred_at": datetime.utcnow().isoformat(),
        "details": event_details,
    }


def _build_feishu_payload(channel_type: str, event_type: str, project_name: str, event_details: Dict[str, Any]) -> Dict[str, Any]:
    status_color = {
        "deployment_success": "green",
        "deployment_failed": "red",
        "agent_offline": "orange",
        "health_degraded": "orange",
        "health_unhealthy": "red",
        "health_recovered": "green",
        "agent_recovered": "green",
        "test": "blue",
    }

    status_title = {
        "deployment_success": "Deployed Successfully",
        "deployment_failed": "Deploy Failed",
        "agent_offline": "Agent Offline",
        "health_degraded": "Degraded",
        "health_unhealthy": "Health Check Failed",
        "health_recovered": "Health Recovered",
        "agent_recovered": "Agent Recovered",
        "test": "Test Notification",
    }

    lines = [f"**Project**: {project_name}"]
    if event_details.get("commit_hash"):
        lines.append(f"**Commit**: `{event_details['commit_hash'][:8]}`")
    if event_details.get("deployment_id"):
        lines.append(f"**Deployment**: #{event_details['deployment_id']}")
    if event_details.get("error_code"):
        lines.append(f"**Error**: {event_details['error_code']}")
    if event_details.get("agent_id"):
        lines.append(f"**Agent**: {event_details['agent_id']}")
    if event_details.get("message"):
        lines.append(f"**Message**: {event_details['message']}")

    return {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{status_title.get(event_type, '通知')}",
                },
                "template": status_color.get(event_type, "blue"),
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "\n".join(lines),
                    },
                }
            ],
        },
    }


def _build_slack_payload(channel_type: str, event_type: str, project_name: str, event_details: Dict[str, Any]) -> Dict[str, Any]:
    status_color = {
        "deployment_success": "#2eb886",
        "deployment_failed": "#a30200",
        "agent_offline": "#daa038",
        "health_degraded": "#daa038",
        "health_unhealthy": "#da1f26",
        "health_recovered": "#2eb886",
        "agent_recovered": "#2eb886",
        "test": "#4287f5",
    }

    status_title = {
        "deployment_success": "Deployment Success",
        "deployment_failed": "Deployment Failed",
        "agent_offline": "Agent Offline",
        "health_degraded": "Health Degraded",
        "health_unhealthy": "Service Unhealthy",
        "health_recovered": "Service Recovered",
        "agent_recovered": "Agent Recovered",
        "test": "Test Notification",
    }

    fields = [
        {"title": "Project", "value": project_name, "short": True},
    ]

    if event_details.get("commit_hash"):
        fields.append({"title": "Commit", "value": f"`{event_details['commit_hash'][:8]}`", "short": True})
    if event_details.get("deployment_id"):
        fields.append({"title": "Deployment", "value": f"#{event_details['deployment_id']}", "short": True})
    if event_details.get("error_code"):
        fields.append({"title": "Error", "value": event_details["error_code"], "short": True})
    if event_details.get("agent_id"):
        fields.append({"title": "Agent", "value": event_details["agent_id"], "short": True})
    if event_details.get("message"):
        fields.append({"title": "Message", "value": event_details["message"], "short": False})

    return {
        "text": f"{status_title.get(event_type, 'Notification')}: {project_name}",
        "attachments": [
            {
                "color": status_color.get(event_type, "#4287f5"),
                "fields": fields,
                "ts": int(datetime.utcnow().timestamp()),
            }
        ],
    }


def _build_payload(channel_type: str, event_type: str, project_name: str, event_details: Dict[str, Any]) -> Dict[str, Any]:
    if channel_type == "feishu":
        return _build_feishu_payload(channel_type, event_type, project_name, event_details)
    elif channel_type == "slack":
        return _build_slack_payload(channel_type, event_type, project_name, event_details)
    else:
        return _build_generic_webhook_payload(channel_type, event_type, project_name, event_details)


def _send_notification(
    channel: Any,
    event_type: str,
    project_name: str,
    event_details: Dict[str, Any],
) -> Tuple[bool, Optional[int], str]:
    channel_type = channel.channel_type
    config = channel.config or {}

    if channel_type == "feishu":
        url = config.get("webhook_url")
        timeout = config.get("timeout_seconds", DEFAULT_TIMEOUT)
        payload = _build_payload(channel_type, event_type, project_name, event_details)
        return _send_http_request(url, method="POST", data=payload, timeout=timeout)

    elif channel_type == "slack":
        url = config.get("webhook_url")
        timeout = config.get("timeout_seconds", DEFAULT_TIMEOUT)
        payload = _build_payload(channel_type, event_type, project_name, event_details)
        return _send_http_request(url, method="POST", data=payload, timeout=timeout)

    else:
        url = config.get("url")
        method = config.get("method", "POST")
        headers = config.get("headers", {})
        timeout = config.get("timeout_seconds", DEFAULT_TIMEOUT)
        payload = _build_payload(channel_type, event_type, project_name, event_details)
        return _send_http_request(url, method=method, headers=headers, data=payload, timeout=timeout)


def send_notification_for_channel(
    db: Session,
    channel: Any,
    project: Any,
    event_type: str,
    event_details: Dict[str, Any],
    setting: Optional[Any] = None,
) -> Any:
    from shipsmith_db import NotificationDelivery

    fingerprint = _build_fingerprint(project.id, event_type, event_details)
    is_recovery = _is_recovery_event(event_type)

    cooldown_seconds = 0
    send_recovery = True
    if setting:
        cooldown_seconds = getattr(setting, "cooldown_seconds", 0)
        send_recovery = getattr(setting, "send_recovery", True)

    is_suppressed = False
    if _is_error_event(event_type):
        is_suppressed = _should_suppress(
            db=db,
            project_id=project.id,
            channel_id=channel.id,
            event_type=event_type,
            fingerprint=fingerprint,
            cooldown_seconds=cooldown_seconds,
            send_recovery=send_recovery,
            is_recovery=is_recovery,
        )

    if is_recovery and not send_recovery:
        delivery = NotificationDelivery(
            channel_id=channel.id,
            project_id=project.id,
            event_type=event_type,
            fingerprint=fingerprint,
            is_recovery=True,
            is_suppressed=True,
            status="suppressed",
            payload=event_details,
        )
        db.add(delivery)
        db.flush()
        db.commit()
        db.refresh(delivery)
        return delivery

    if is_suppressed:
        delivery = NotificationDelivery(
            channel_id=channel.id,
            project_id=project.id,
            event_type=event_type,
            fingerprint=fingerprint,
            is_recovery=False,
            is_suppressed=True,
            status="suppressed",
            payload=event_details,
        )
        db.add(delivery)
        db.flush()
        db.commit()
        db.refresh(delivery)
        return delivery

    delivery = NotificationDelivery(
        channel_id=channel.id,
        project_id=project.id,
        event_type=event_type,
        fingerprint=fingerprint,
        is_recovery=is_recovery,
        is_suppressed=False,
        status="queued",
        payload=event_details,
    )
    db.add(delivery)
    db.flush()

    try:
        success, status_code, response_text = _send_notification(
            channel, event_type, project.name, event_details
        )

        delivery.status = "success" if success else "failed"
        delivery.sent_at = datetime.utcnow()
        if not success:
            delivery.error_message = response_text[:2000] if response_text else "Unknown error"

        db.commit()
        db.refresh(delivery)
    except Exception as e:
        delivery.status = "failed"
        delivery.error_message = str(e)[:2000]
        db.commit()
        db.refresh(delivery)

    return delivery


def get_active_channels_for_event(db: Session, project_id: int, event_type: str) -> Tuple[List[Any], Optional[Any]]:
    from shipsmith_db import NotificationChannel, ProjectNotificationSetting

    setting = (
        db.query(ProjectNotificationSetting)
        .filter(
            ProjectNotificationSetting.project_id == project_id,
            ProjectNotificationSetting.event_type == event_type,
        )
        .first()
    )

    if not setting or not setting.enabled or not setting.channel_ids:
        return [], None

    channels = (
        db.query(NotificationChannel)
        .filter(
            NotificationChannel.project_id == project_id,
            NotificationChannel.id.in_(setting.channel_ids),
            NotificationChannel.is_active == True,
        )
        .all()
    )

    return channels, setting


def dispatch_notification(
    db: Session,
    project_id: int,
    event_type: str,
    event_details: Dict[str, Any],
) -> List[Any]:
    from shipsmith_db import Project

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return []

    channels, setting = get_active_channels_for_event(db, project_id, event_type)
    if not channels:
        return []

    deliveries = []
    for channel in channels:
        delivery = send_notification_for_channel(
            db, channel, project, event_type, event_details, setting
        )
        deliveries.append(delivery)

    return deliveries


async def dispatch_notification_async(
    db: Session,
    project_id: int,
    event_type: str,
    event_details: Dict[str, Any],
) -> List[Any]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        dispatch_notification,
        db,
        project_id,
        event_type,
        event_details,
    )


def get_event_details_for_deployment(deployment: Any) -> Dict[str, Any]:
    return {
        "deployment_id": deployment.id,
        "kind": deployment.kind,
        "commit_hash": deployment.commit_hash,
        "status": deployment.status,
        "trigger_source": deployment.trigger_source,
        "triggered_by": deployment.triggered_by,
        "error_code": deployment.error_code,
        "failure_phase": deployment.failure_phase,
        "started_at": deployment.started_at.isoformat() if deployment.started_at else None,
        "finished_at": deployment.finished_at.isoformat() if deployment.finished_at else None,
    }
