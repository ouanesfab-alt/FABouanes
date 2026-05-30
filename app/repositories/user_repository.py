from __future__ import annotations

from app.core.db_access import db_task, execute_db, query_db
from app.core.permissions import normalize_role


@db_task
def get_user_by_username(username: str):
    row = query_db("SELECT * FROM users WHERE username = %s", (username,), one=True)
    return dict(row) if row else None


@db_task
def get_user_by_id(user_id: int):
    row = query_db("SELECT * FROM users WHERE id = %s", (user_id,), one=True)
    return dict(row) if row else None


@db_task
def user_exists(username: str) -> bool:
    return get_user_by_username(username) is not None


@db_task
def create_user(
    username: str,
    password_hash: str,
    role: str = "operator",
    must_change_password: bool = False,
    is_active: bool = True,
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
        ) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """,
        (username, password_hash, normalize_role(role), bool(must_change_password), bool(is_active)),
    )


@db_task
def update_password(user_id: int, password_hash: str, must_change_password: bool = False) -> int:
    return execute_db(
        """
        UPDATE users
        SET password_hash = %s,
            must_change_password = %s,
            last_password_change_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (password_hash, bool(must_change_password), user_id),
    )


@db_task
def update_user_role_and_status(user_id: int, role: str, is_active: bool) -> int:
    return execute_db(
        "UPDATE users SET role = %s, is_active = %s WHERE id = %s",
        (normalize_role(role), bool(is_active), user_id),
    )


@db_task
def touch_login(user_id: int) -> int:
    return execute_db("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = %s", (user_id,))


@db_task
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
