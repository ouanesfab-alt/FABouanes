"""Modèles SQLModel pour le module Users."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

from app.core.model_utils import _now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="operator")
    must_change_password: bool = Field(default=False)
    is_active: bool = Field(default=True)
    last_login_at: Optional[datetime] = Field(default=None)
    last_password_change_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    xp: int = Field(default=0)
    level: int = Field(default=1)


class UserBadge(SQLModel, table=True):
    __tablename__ = "user_badges"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    badge_name: str = Field(index=True)
    badge_title: str
    badge_description: str
    unlocked_at: datetime = Field(default_factory=_now)
