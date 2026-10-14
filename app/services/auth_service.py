# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour auth_service.
Désormais hébergé dans app.modules.users.service.
"""

from __future__ import annotations

import sys
from app.modules.users import service as _mod
from app.modules.users.service import (  # noqa: F401
    VALID_ROLES,
    attempt_login,
    change_user_password,
    generate_password_hash,
    get_user_by_id,
    get_user_by_username,
    touch_login,
    update_password,
    validate_new_user_payload,
    verify_credentials,
)

# Mirror any remaining module attributes dynamically
for _name in dir(_mod):
    if not _name.startswith("__"):
        setattr(sys.modules[__name__], _name, getattr(_mod, _name))

__all__ = [
    "VALID_ROLES",
    "attempt_login",
    "change_user_password",
    "generate_password_hash",
    "get_user_by_id",
    "get_user_by_username",
    "touch_login",
    "update_password",
    "validate_new_user_payload",
    "verify_credentials",
]
