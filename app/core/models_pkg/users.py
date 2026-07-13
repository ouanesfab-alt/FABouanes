"""Modèles SQLModel pour le module Users."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from sqlmodel import SQLModel, Field
from pydantic import field_validator

from app.core.model_utils import _now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    role: str = Field(default="operator")
    must_change_password: bool = Field(default=False)
    is_active: bool = Field(default=True)
    custom_permissions_json: str = Field(default="[]")
    last_login_at: Optional[datetime] = Field(default=None)
    last_password_change_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=_now)
    xp: int = Field(default=0)
    level: int = Field(default=1)

    @property
    def custom_permissions_list(self) -> list[str]:
        import json
        try:
            return json.loads(self.custom_permissions_json or "[]")
        except Exception:
            return []

    @field_validator("must_change_password", "is_active", mode="before")
    @classmethod
    def _coerce_bool(cls, v: Any) -> bool:
        """Coerce les entiers 0/1 retournés par SQLite en booléens Python."""
        if isinstance(v, int):
            return bool(v)
        return v


class UserBadge(SQLModel, table=True):
    __tablename__ = "user_badges"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", index=True)
    badge_name: str = Field(index=True)
    badge_title: str
    badge_description: str
    unlocked_at: datetime = Field(default_factory=_now)
