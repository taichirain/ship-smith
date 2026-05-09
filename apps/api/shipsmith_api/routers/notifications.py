from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..schemas import (
    NotificationChannelCreate,
    NotificationChannelUpdate,
    NotificationChannelResponse,
    ProjectNotificationSettingBase,
    ProjectNotificationSettingUpdate,
    ProjectNotificationSettingResponse,
    NotificationDeliveryResponse,
    TestNotificationRequest,
    TestNotificationResponse,
    NotificationEventType,
)
from ..notifications import (
    dispatch_notification,
    send_notification_for_channel,
)


router = APIRouter(prefix="/notifications", tags=["notifications"])


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import NotificationChannel, ProjectNotificationSetting, Project
    return NotificationChannel, ProjectNotificationSetting, Project


def _get_project_for_user(db: Session, project_id: int, current_user: dict) -> object:
    _, _, Project = _import_db_models()
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project with id {project_id} not found",
        )
    
    return project


DEFAULT_NOTIFICATION_EVENTS = [
    "deployment_success",
    "deployment_failed",
    "agent_offline",
    "health_degraded",
    "health_unhealthy",
    "health_recovered",
]


@router.get("/channels", response_model=List[NotificationChannelResponse])
async def list_channels(
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, _ = _import_db_models()
    
    query = db.query(NotificationChannel)
    if project_id is not None:
        _get_project_for_user(db, project_id, current_user)
        query = query.filter(NotificationChannel.project_id == project_id)
    
    return query.order_by(NotificationChannel.created_at.desc()).all()


@router.post("/channels", response_model=NotificationChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: NotificationChannelCreate,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, _ = _import_db_models()
    
    if project_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id is required",
        )
    
    _get_project_for_user(db, project_id, current_user)
    
    channel = NotificationChannel(
        project_id=project_id,
        name=data.name,
        channel_type=data.channel_type,
        is_active=data.is_active,
        config=data.config.model_dump(),
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    return channel


@router.get("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def get_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, _ = _import_db_models()
    
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification channel with id {channel_id} not found",
        )
    
    return channel


@router.patch("/channels/{channel_id}", response_model=NotificationChannelResponse)
async def update_channel(
    channel_id: int,
    data: NotificationChannelUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, _ = _import_db_models()
    
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification channel with id {channel_id} not found",
        )
    
    if data.name is not None:
        channel.name = data.name
    if data.is_active is not None:
        channel.is_active = data.is_active
    if data.config is not None:
        channel.config = data.config.model_dump()
    
    channel.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(channel)
    
    return channel


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel(
    channel_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, _ = _import_db_models()
    
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification channel with id {channel_id} not found",
        )
    
    db.delete(channel)
    db.commit()


@router.get("/settings", response_model=List[ProjectNotificationSettingResponse])
async def list_settings(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, ProjectNotificationSetting, _ = _import_db_models()
    
    _get_project_for_user(db, project_id, current_user)
    
    settings = (
        db.query(ProjectNotificationSetting)
        .filter(ProjectNotificationSetting.project_id == project_id)
        .order_by(ProjectNotificationSetting.event_type.asc())
        .all()
    )
    
    existing_event_types = {s.event_type for s in settings}
    for event_type in DEFAULT_NOTIFICATION_EVENTS:
        if event_type not in existing_event_types:
            setting = ProjectNotificationSetting(
                project_id=project_id,
                event_type=event_type,
                enabled=False,
                channel_ids=[],
            )
            db.add(setting)
            settings.append(setting)
    
    db.commit()
    for s in settings:
        db.refresh(s)
    
    return settings


@router.get("/settings/{setting_id}", response_model=ProjectNotificationSettingResponse)
async def get_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, ProjectNotificationSetting, _ = _import_db_models()
    
    setting = (
        db.query(ProjectNotificationSetting)
        .filter(ProjectNotificationSetting.id == setting_id)
        .first()
    )
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification setting with id {setting_id} not found",
        )
    
    return setting


@router.post("/settings", response_model=ProjectNotificationSettingResponse, status_code=status.HTTP_201_CREATED)
async def create_setting(
    data: ProjectNotificationSettingBase,
    project_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, ProjectNotificationSetting, _ = _import_db_models()

    if project_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="project_id is required",
        )

    _get_project_for_user(db, project_id, current_user)

    existing = (
        db.query(ProjectNotificationSetting)
        .filter(
            ProjectNotificationSetting.project_id == project_id,
            ProjectNotificationSetting.event_type == data.event_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Setting for event_type '{data.event_type}' already exists. Use PATCH to update.",
        )

    setting = ProjectNotificationSetting(
        project_id=project_id,
        event_type=data.event_type,
        enabled=data.enabled,
        channel_ids=data.channel_ids,
        cooldown_seconds=data.cooldown_seconds,
        send_recovery=data.send_recovery,
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)

    return setting


@router.patch("/settings/{setting_id}", response_model=ProjectNotificationSettingResponse)
async def update_setting(
    setting_id: int,
    data: ProjectNotificationSettingUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, ProjectNotificationSetting, _ = _import_db_models()

    setting = (
        db.query(ProjectNotificationSetting)
        .filter(ProjectNotificationSetting.id == setting_id)
        .first()
    )
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification setting with id {setting_id} not found",
        )

    if data.enabled is not None:
        setting.enabled = data.enabled
    if data.channel_ids is not None:
        setting.channel_ids = data.channel_ids
    if data.cooldown_seconds is not None:
        setting.cooldown_seconds = data.cooldown_seconds
    if data.send_recovery is not None:
        setting.send_recovery = data.send_recovery

    setting.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(setting)

    return setting


@router.delete("/settings/{setting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, ProjectNotificationSetting, _ = _import_db_models()
    
    setting = (
        db.query(ProjectNotificationSetting)
        .filter(ProjectNotificationSetting.id == setting_id)
        .first()
    )
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification setting with id {setting_id} not found",
        )
    
    db.delete(setting)
    db.commit()


@router.post("/test", response_model=TestNotificationResponse)
async def test_notification(
    data: TestNotificationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    NotificationChannel, _, Project = _import_db_models()
    
    channel = db.query(NotificationChannel).filter(NotificationChannel.id == data.channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification channel with id {data.channel_id} not found",
        )
    
    project = db.query(Project).filter(Project.id == channel.project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project for channel not found",
        )
    
    event_type = data.event_type or "deployment_success"
    event_details = {
        "message": "Test notification from ShipSmith",
        "test": True,
    }
    
    delivery = send_notification_for_channel(
        db, channel, project, event_type, event_details
    )
    
    return TestNotificationResponse(
        success=delivery.status == "success",
        message=delivery.error_message or "Notification sent successfully",
        status_code=None,
    )


@router.get("/deliveries", response_model=List[NotificationDeliveryResponse])
async def list_deliveries(
    project_id: int,
    channel_id: Optional[int] = None,
    event_type: Optional[NotificationEventType] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import NotificationDelivery
    
    _get_project_for_user(db, project_id, current_user)
    
    query = db.query(NotificationDelivery).filter(NotificationDelivery.project_id == project_id)
    
    if channel_id is not None:
        query = query.filter(NotificationDelivery.channel_id == channel_id)
    if event_type is not None:
        query = query.filter(NotificationDelivery.event_type == event_type)
    
    return query.order_by(NotificationDelivery.created_at.desc()).limit(limit).all()
