from __future__ import annotations

from typing import Generic, Type, TypeVar, Optional, List, Any
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T", bound=SQLModel)

class AsyncRepository(Generic[T]):
    """Generic asynchronous repository providing common CRUD operations using SQLModel."""
    
    def __init__(self, session: AsyncSession, model_cls: Type[T]):
        self.session = session
        self.model_cls = model_cls

    async def get(self, id_val: Any) -> Optional[T]:
        """Fetch a single record by primary key."""
        return await self.session.get(self.model_cls, id_val)

    async def list(self, offset: int = 0, limit: int = 100) -> List[T]:
        """Fetch multiple records with optional pagination."""
        statement = select(self.model_cls).offset(offset).limit(limit)
        results = await self.session.execute(statement)
        return list(results.scalars().all())

    async def create(self, entity: T) -> T:
        """Persist a new entity to the database."""
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def update(self, entity: T) -> T:
        """Update an existing entity."""
        self.session.add(entity)
        await self.session.commit()
        await self.session.refresh(entity)
        return entity

    async def delete(self, id_val: Any) -> bool:
        """Remove a record by its primary key."""
        entity = await self.get(id_val)
        if not entity:
            return False
        await self.session.delete(entity)
        await self.session.commit()
        return True

    async def count(self) -> int:
        """Count the total number of records in this table."""
        from sqlalchemy import func
        statement = select(func.count()).select_from(self.model_cls)
        results = await self.session.execute(statement)
        return results.scalar() or 0
