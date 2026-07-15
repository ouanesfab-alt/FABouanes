from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.infrastructure.repository import (
    create_user,
    update_password,
    update_user_role_and_status,
    touch_login,
    delete_user,
)


class UsersCommands:
    """Commandes (écritures) pour le module Users."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "operator",
        must_change_password: bool = False,
        is_active: bool = True,
    ) -> int:
        return await create_user(
            username=username,
            password_hash=password_hash,
            role=role,
            must_change_password=must_change_password,
            is_active=is_active,
            db=self.session,
        )

    async def update_password(
        self,
        user_id: int,
        password_hash: str,
        must_change_password: bool = False,
    ) -> int:
        return await update_password(
            user_id=user_id,
            password_hash=password_hash,
            must_change_password=must_change_password,
            db=self.session,
        )

    async def update_user_role_and_status(
        self,
        user_id: int,
        role: str,
        is_active: bool,
    ) -> int:
        return await update_user_role_and_status(
            user_id=user_id,
            role=role,
            is_active=is_active,
            db=self.session,
        )

    async def touch_login(self, user_id: int) -> int:
        return await touch_login(user_id=user_id, db=self.session)

    async def delete_user(self, user_id: int) -> bool:
        return await delete_user(user_id=user_id, db=self.session)
