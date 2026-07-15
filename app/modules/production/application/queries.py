from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.perf_cache import async_cached_result
from app.modules.catalog.infrastructure.repository import list_production_page_context, production_form_context


class ProductionQueries:
    """Gestion des requêtes en lecture seule (Queries) du module Production."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def productions_context(self, args: dict = None) -> dict:
        args = args or {}
        cache_key = tuple(sorted((str(key), str(value)) for key, value in dict(args).items()))
        return await async_cached_result(
            ("productions_context", cache_key),
            lambda: list_production_page_context(args),
            ttl_seconds=30.0
        )

    async def new_production_context(self) -> dict:
        return await production_form_context()
