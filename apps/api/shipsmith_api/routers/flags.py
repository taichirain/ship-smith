from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_db, get_current_user
from ..schemas import (
    FeatureFlagCreate,
    FeatureFlagPatch,
    FeatureFlagResponse,
    FlagAuditResponse,
)


router = APIRouter(prefix="", tags=["flags"])


def _import_db_models():
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
    from shipsmith_db import Project, FeatureFlag, FlagAudit
    return Project, FeatureFlag, FlagAudit


@router.get("/projects/{project_id}/flags", response_model=List[FeatureFlagResponse])
async def list_flags(
    project_id: int,
    include_archived: bool = False,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, FeatureFlag, _ = _import_db_models()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    query = db.query(FeatureFlag).filter(FeatureFlag.project_id == project_id)
    if not include_archived:
        query = query.filter(FeatureFlag.archived == False)

    flags = query.order_by(FeatureFlag.key.asc()).all()
    return [FeatureFlagResponse.model_validate(f) for f in flags]


@router.get("/projects/{project_id}/flags/snapshot")
async def get_flags_snapshot(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, FeatureFlag, _ = _import_db_models()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    flags = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.project_id == project_id,
            FeatureFlag.archived == False,
        )
        .all()
    )

    max_version = max((f.version for f in flags), default=0)
    flags_dict = {f.key: f.enabled for f in flags}

    return {
        "project_id": project_id,
        "version": max_version,
        "flags_count": len(flags),
        "flags": flags_dict,
        "updated_at": max((f.updated_at for f in flags), default=None),
    }


@router.post("/projects/{project_id}/flags", response_model=FeatureFlagResponse, status_code=status.HTTP_201_CREATED)
async def create_flag(
    project_id: int,
    data: FeatureFlagCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, FeatureFlag, FlagAudit = _import_db_models()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    existing = (
        db.query(FeatureFlag)
        .filter(
            FeatureFlag.project_id == project_id,
            FeatureFlag.key == data.key,
        )
        .first()
    )
    
    if existing:
        if existing.archived:
            existing.archived = False
            existing.archived_at = None
            existing.archived_by = None
            existing.enabled = data.enabled
            existing.description = data.description
            existing.version += 1
            existing.updated_by = current_user.get("username")
            existing.updated_at = datetime.utcnow()
            
            audit = FlagAudit(
                project_id=project_id,
                flag_key=data.key,
                old_enabled=None,
                new_enabled=data.enabled,
                changed_by=current_user.get("username"),
            )
            db.add(audit)
            db.commit()
            db.refresh(existing)
            return FeatureFlagResponse.model_validate(existing)
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Flag with key '{data.key}' already exists",
            )

    flag = FeatureFlag(
        project_id=project_id,
        key=data.key,
        enabled=data.enabled,
        description=data.description,
        version=1,
        updated_by=current_user.get("username"),
    )
    db.add(flag)
    db.flush()

    audit = FlagAudit(
        project_id=project_id,
        flag_key=data.key,
        old_enabled=None,
        new_enabled=data.enabled,
        changed_by=current_user.get("username"),
    )
    db.add(audit)

    db.commit()
    db.refresh(flag)

    return FeatureFlagResponse.model_validate(flag)


@router.patch("/flags/{flag_id}", response_model=FeatureFlagResponse)
async def update_flag(
    flag_id: int,
    data: FeatureFlagPatch,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, FeatureFlag, FlagAudit = _import_db_models()

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found",
        )
    
    if flag.archived:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot update archived flag",
        )

    old_enabled = flag.enabled
    changed = False

    if data.enabled is not None and data.enabled != flag.enabled:
        flag.enabled = data.enabled
        flag.version += 1
        changed = True

    if data.description is not None:
        flag.description = data.description

    if changed:
        audit = FlagAudit(
            project_id=flag.project_id,
            flag_key=flag.key,
            old_enabled=old_enabled,
            new_enabled=flag.enabled,
            changed_by=current_user.get("username"),
        )
        db.add(audit)

    flag.updated_by = current_user.get("username")
    flag.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(flag)

    return FeatureFlagResponse.model_validate(flag)


@router.post("/flags/{flag_id}/archive")
async def archive_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, FeatureFlag, _ = _import_db_models()

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found",
        )

    if flag.archived:
        return {"ok": True, "message": "Flag already archived"}

    flag.archived = True
    flag.archived_at = datetime.utcnow()
    flag.archived_by = current_user.get("username")
    flag.version += 1

    db.commit()

    return {
        "ok": True,
        "flag_id": flag.id,
        "flag_key": flag.key,
        "archived": True,
        "archived_at": flag.archived_at.isoformat() if flag.archived_at else None,
    }


@router.post("/flags/{flag_id}/unarchive")
async def unarchive_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, FeatureFlag, _ = _import_db_models()

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found",
        )

    if not flag.archived:
        return {"ok": True, "message": "Flag already active"}

    flag.archived = False
    flag.archived_at = None
    flag.archived_by = None
    flag.version += 1
    flag.updated_by = current_user.get("username")
    flag.updated_at = datetime.utcnow()

    db.commit()

    return {
        "ok": True,
        "flag_id": flag.id,
        "flag_key": flag.key,
        "archived": False,
    }


@router.delete("/flags/{flag_id}")
async def delete_flag(
    flag_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    _, FeatureFlag, _ = _import_db_models()

    flag = db.query(FeatureFlag).filter(FeatureFlag.id == flag_id).first()
    if not flag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Flag not found",
        )

    db.delete(flag)
    db.commit()

    return {"ok": True, "flag_id": flag_id, "deleted": True}


@router.get("/projects/{project_id}/flags/audits", response_model=List[FlagAuditResponse])
async def list_flag_audits(
    project_id: int,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    Project, _, FlagAudit = _import_db_models()

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    audits = (
        db.query(FlagAudit)
        .filter(FlagAudit.project_id == project_id)
        .order_by(FlagAudit.created_at.desc())
        .limit(limit)
        .all()
    )
    return [FlagAuditResponse.model_validate(a) for a in audits]
