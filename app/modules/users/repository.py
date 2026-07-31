from __future__ import annotations

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.async_db import get_async_sessionmaker
from app.core.helpers import db_task_compat
from app.core.permissions import normalize_role
from app.core.models import User
from app.core.base_repository import AsyncRepository


class UserRepository(AsyncRepository[User]):
    """Asynchronous repository for the User model."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)


@db_task_compat
async def get_user_by_username(username: str, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_user_by_username_impl(username, session)
    return await _get_user_by_username_impl(username, db)


async def _get_user_by_username_impl(username: str, db: AsyncSession):
    stmt = select(User).where(User.username == username)
    res = await db.execute(stmt)
    user = res.scalars().first()
    return user.model_dump() if user else None


@db_task_compat
async def get_user_by_id(user_id: int, db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _get_user_by_id_impl(user_id, session)
    return await _get_user_by_id_impl(user_id, db)


async def _get_user_by_id_impl(user_id: int, db: AsyncSession):
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalars().first()
    return user.model_dump() if user else None


@db_task_compat
async def user_exists(username: str, db: AsyncSession | None = None) -> bool:
    user = await get_user_by_username(username, db=db)
    return user is not None


@db_task_compat
async def create_user(
    username: str,
    password_hash: str,
    role: str = "operator",
    must_change_password: bool = False,
    is_active: bool = True,
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _create_user_impl(username, password_hash, role, must_change_password, is_active, session)
            await session.commit()
            return res
    return await _create_user_impl(username, password_hash, role, must_change_password, is_active, db)


async def _create_user_impl(
    username: str,
    password_hash: str,
    role: str,
    must_change_password: bool,
    is_active: bool,
    db: AsyncSession,
) -> int:
    new_user = User(
        username=username,
        password_hash=password_hash,
        role=normalize_role(role),
        must_change_password=must_change_password,
        is_active=is_active,
    )
    db.add(new_user)
    await db.flush()
    return new_user.id


@db_task_compat
async def update_password(
    user_id: int,
    password_hash: str,
    must_change_password: bool = False,
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _update_password_impl(user_id, password_hash, must_change_password, session)
            await session.commit()
            return res
    return await _update_password_impl(user_id, password_hash, must_change_password, db)


async def _update_password_impl(
    user_id: int,
    password_hash: str,
    must_change_password: bool,
    db: AsyncSession,
) -> int:
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(
            password_hash=password_hash,
            must_change_password=must_change_password,
            last_password_change_at=func.current_timestamp(),
        )
    )
    res = await db.execute(stmt)
    return res.rowcount


@db_task_compat
async def update_user_role_and_status(
    user_id: int,
    role: str,
    is_active: bool,
    db: AsyncSession | None = None,
) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _update_user_role_and_status_impl(user_id, role, is_active, session)
            await session.commit()
            return res
    return await _update_user_role_and_status_impl(user_id, role, is_active, db)


async def _update_user_role_and_status_impl(
    user_id: int,
    role: str,
    is_active: bool,
    db: AsyncSession,
) -> int:
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(
            role=normalize_role(role),
            is_active=is_active,
        )
    )
    res = await db.execute(stmt)
    return res.rowcount


@db_task_compat
async def touch_login(user_id: int, db: AsyncSession | None = None) -> int:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _touch_login_impl(user_id, session)
            await session.commit()
            return res
    return await _touch_login_impl(user_id, db)


async def _touch_login_impl(user_id: int, db: AsyncSession) -> int:
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(
            last_login_at=func.current_timestamp(),
        )
    )
    res = await db.execute(stmt)
    return res.rowcount


@db_task_compat
async def list_users(db: AsyncSession | None = None):
    if db is None:
        async with get_async_sessionmaker()() as session:
            return await _list_users_impl(session)
    return await _list_users_impl(db)


async def _list_users_impl(db: AsyncSession):
    stmt = select(
        User.id,
        User.username,
        User.role,
        User.is_active,
        User.must_change_password,
        User.created_at,
        User.last_login_at,
        User.last_password_change_at,
    ).order_by(User.id.desc())
    res = await db.execute(stmt)
    return [dict(row._mapping) for row in res.all()]


@db_task_compat
async def delete_user(user_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _delete_user_impl(user_id, session)
            await session.commit()
            return res
    return await _delete_user_impl(user_id, db)


async def _delete_user_impl(user_id: int, db: AsyncSession) -> bool:
    from sqlalchemy import delete
    from app.core.models_pkg.users import UserBadge

    # Supprimer d'abord les badges
    await db.execute(delete(UserBadge).where(UserBadge.user_id == user_id))

    # Supprimer l'utilisateur
    stmt = delete(User).where(User.id == user_id)
    res = await db.execute(stmt)
    return res.rowcount > 0


@db_task_compat
async def record_account_login_failure(
    user_id: int,
    max_attempts: int = 5,
    lockout_minutes: int = 15,
    db: AsyncSession | None = None,
) -> tuple[int, bool]:
    """Increments failed_login_count. If count >= max_attempts, locks account for lockout_minutes."""
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _record_account_login_failure_impl(user_id, max_attempts, lockout_minutes, session)
            await session.commit()
            return res
    return await _record_account_login_failure_impl(user_id, max_attempts, lockout_minutes, db)


async def _record_account_login_failure_impl(
    user_id: int,
    max_attempts: int,
    lockout_minutes: int,
    db: AsyncSession,
) -> tuple[int, bool]:
    from datetime import datetime, timedelta
    from sqlalchemy import func
    stmt = (
        update(User)
        .where(User.id == user_id)
        .values(failed_login_count=func.coalesce(User.failed_login_count, 0) + 1)
        .returning(User.failed_login_count)
    )
    res = await db.execute(stmt)
    row = res.scalar_one_or_none()
    new_count = row if isinstance(row, int) else 1

    is_locked = False
    if new_count >= max_attempts:
        lock_until = datetime.now() + timedelta(minutes=lockout_minutes)
        await db.execute(
            update(User).where(User.id == user_id).values(locked_until=lock_until)
        )
        is_locked = True

    return new_count, is_locked


@db_task_compat
async def reset_account_login_failures(user_id: int, db: AsyncSession | None = None) -> None:
    if db is None:
        async with get_async_sessionmaker()() as session:
            await _reset_account_login_failures_impl(user_id, session)
            await session.commit()
            return
    await _reset_account_login_failures_impl(user_id, db)


async def _reset_account_login_failures_impl(user_id: int, db: AsyncSession) -> None:
    stmt = update(User).where(User.id == user_id).values(failed_login_count=0, locked_until=None)
    await db.execute(stmt)


@db_task_compat
async def unlock_user_account(user_id: int, db: AsyncSession | None = None) -> bool:
    if db is None:
        async with get_async_sessionmaker()() as session:
            res = await _unlock_user_account_impl(user_id, session)
            await session.commit()
            return res
    return await _unlock_user_account_impl(user_id, db)


async def _unlock_user_account_impl(user_id: int, db: AsyncSession) -> bool:
    user_stmt = select(User.username).where(User.id == user_id)
    res = await db.execute(user_stmt)
    uname = res.scalar_one_or_none()
    if uname:
        from app.core.rate_limit_store import RateLimitStore
        RateLimitStore.clear_user(uname)
    stmt = update(User).where(User.id == user_id).values(failed_login_count=0, locked_until=None)
    res_up = await db.execute(stmt)
    return res_up.rowcount > 0
