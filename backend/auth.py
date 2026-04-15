from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from database import get_db
from models import User, SessionToken

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

TOKEN_TTL_MINUTES = int(os.getenv("APP_TOKEN_TTL_MINUTES", "720"))

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)

def create_token(db: Session, user: User) -> SessionToken:
    token_value = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires = now + timedelta(minutes=TOKEN_TTL_MINUTES)
    tok = SessionToken(token=token_value, user_id=user.id, expires_at=expires)
    db.add(tok)
    db.commit()
    db.refresh(tok)
    return tok

def get_user_by_token(db: Session, token_value: str) -> Optional[User]:
    now = datetime.now(timezone.utc)
    tok = db.query(SessionToken).filter(SessionToken.token == token_value).first()
    if not tok:
        return None
    if tok.expires_at < now:
        # token expired; delete it
        db.delete(tok)
        db.commit()
        return None
    return db.query(User).filter(User.id == tok.user_id, User.is_active == True).first()  # noqa: E712

def require_auth(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), db: Session = Depends(get_db)) -> User:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = get_user_by_token(db, credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user

def require_role(role: str):
    def _checker(user: User = Depends(require_auth)) -> User:
        if user.role != role:
            raise HTTPException(status_code=403, detail=f"Requires role '{role}'")
        return user
    return _checker
