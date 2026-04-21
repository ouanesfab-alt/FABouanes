from __future__ import annotations

from fabouanes.core.db_access import execute_db, query_db
from fabouanes.core.permissions import normalize_role


def get_user_by_username(username: str):
    row = query_db("SELECT * FROM users WHERE username = ?", (username,), one=True)
    return dict(row) if row else None


def get_user_by_id(user_id: int):
    row = query_db("SELECT * FROM users WHERE id = ?", (user_id,), one=True)
    return dict(row) if row else None


def user_exists(username: str) -> bool:
    return get_user_by_username(username) is not None


def create_user(
    username: str,
    password_hash: str,
    role: str = "operator",
    must_change_password: int = 0,
    is_active: int = 1,
) -> int:
    return execute_db(
        """
        INSERT INTO users (
            username,
            password_hash,
            role,
            must_change_password,
            is_active,
            last_password_change_at
        ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (username, password_hash, normalize_role(role), must_change_password, int(bool(is_active))),
    )


def update_password(user_id: int, password_hash: str, must_change_password: int = 0) -> int:
    return execute_db(
        """
        UPDATE users
        SET password_hash = ?,
            must_change_password = ?,
            last_password_change_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (password_hash, must_change_password, user_id),
    )


def update_user_role_and_status(user_id: int, role: str, is_active: int) -> int:
    return execute_db(
        "UPDATE users SET role = ?, is_active = ? WHERE id = ?",
        (normalize_role(role), int(bool(is_active)), user_id),
    )


def touch_login(user_id: int) -> int:
    return execute_db("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id,))


def list_users():
    rows = query_db(
        """
        SELECT id,
               username,
               role,
               is_active,
               must_change_password,
               created_at,
               last_login_at,
               last_password_change_at
        FROM users
        ORDER BY id DESC
        """
    )
    return [dict(row) for row in rows]
