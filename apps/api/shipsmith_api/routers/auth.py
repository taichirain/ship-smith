from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..config import get_settings
from ..security import verify_password, create_access_token, hash_password
from ..deps import get_db
from ..schemas import Token

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "packages", "db"))
from shipsmith_db import User


router = APIRouter(prefix="/auth", tags=["auth"])


def ensure_default_user(db: Session):
    settings = get_settings()
    user = db.query(User).filter(User.username == settings.admin_username).first()

    if not user:
        hashed = hash_password(settings.admin_password)
        user = User(
            username=settings.admin_username,
            password_hash=hashed,
        )
        db.add(user)
        db.commit()


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    ensure_default_user(db)

    user = db.query(User).filter(User.username == form_data.username).first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}
