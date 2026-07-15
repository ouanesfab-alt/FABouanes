from __future__ import annotations

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.application.queries import UsersQueries
from app.modules.users.application.commands import UsersCommands


class UsersService:
    """Façade CQRS pour le module Users."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.queries = UsersQueries(session)
        self.commands = UsersCommands(session)

    # ── [QUERIES] ──

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        return await self.queries.get_user_by_username(username)

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        return await self.queries.get_user_by_id(user_id)

    async def user_exists(self, username: str) -> bool:
        return await self.queries.user_exists(username)

    async def list_users(self) -> List[dict]:
        return await self.queries.list_users()

    # ── [COMMANDS] ──

    async def create_user(
        self,
        username: str,
        password_hash: str,
        role: str = "operator",
        must_change_password: bool = False,
        is_active: bool = True,
    ) -> int:
        return await self.commands.create_user(
            username=username,
            password_hash=password_hash,
            role=role,
            must_change_password=must_change_password,
            is_active=is_active,
        )

    async def update_password(
        self,
        user_id: int,
        password_hash: str,
        must_change_password: bool = False,
    ) -> int:
        return await self.commands.update_password(user_id, password_hash, must_change_password)

    async def update_user_role_and_status(self, user_id: int, role: str, is_active: bool) -> int:
        return await self.commands.update_user_role_and_status(user_id, role, is_active)

    async def touch_login(self, user_id: int) -> int:
        return await self.commands.touch_login(user_id)

    async def delete_user(self, user_id: int) -> bool:
        return await self.commands.delete_user(user_id)
