from __future__ import annotations

from pydantic import BaseModel, Field, field_validator
from typing import Optional


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=200)

    @field_validator('username')
    @classmethod
    def username_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Le nom d'utilisateur ne peut pas être vide.")
        return v.strip()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=4, max_length=200)
    confirm_password: str = Field(..., min_length=4, max_length=200)

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError("Les mots de passe ne correspondent pas.")
        return v


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=4, max_length=200)
    role: str = Field('operator', pattern=r'^(admin|manager|operator)$')

    @field_validator('username')
    @classmethod
    def username_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Le nom d'utilisateur ne peut pas être vide.")
        return stripped


class UserUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern=r'^(admin|manager|operator)$')
    is_active: Optional[bool] = None
