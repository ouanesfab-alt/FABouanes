from __future__ import annotations

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.users.infrastructure.repository import (
    get_user_by_username,
    get_user_by_id,
    user_exists,
    list_users,
)


class UsersQueries:
    """Requêtes en lecture seule pour le module Users."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_by_username(self, username: str) -> Optional[dict]:
        return await get_user_by_username(username, db=self.session)

    async def get_user_by_id(self, user_id: int) -> Optional[dict]:
        return await get_user_by_id(user_id, db=self.session)

    async def user_exists(self, username: str) -> bool:
        return await user_exists(username, db=self.session)

    async def list_users(self) -> List[dict]:
        return await list_users(db=self.session)
