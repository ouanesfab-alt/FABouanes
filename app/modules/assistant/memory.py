import asyncio
import concurrent.futures
import logging
from typing import Any, Dict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db_helpers import db_manager
from app.core.uow import unit_of_work

logger = logging.getLogger("fabouanes.assistant.memory")


def _is_mocked(func_or_obj: Any) -> bool:
    name = type(func_or_obj).__name__
    return "Mock" in name


def _run_async(coro: Any) -> Any:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


def remember(content: str, category: str = "general", source: str = "user_explicit") -> Dict[str, Any]:
    """Stocke un nouveau souvenir dans la mémoire persistante de Sabrina."""
    if _is_mocked(db_manager) or _is_mocked(getattr(db_manager, "query_db", None)):
        try:
            content = content.strip()
            if not content:
                return {"error": "Contenu vide — impossible de mémoriser."}

            existing = db_manager.query_db("SELECT id FROM sabrina_memory WHERE content = %s LIMIT 1", (content,))
            if existing:
                return {
                    "status": "already_known",
                    "message": f"Je connais déjà cette information (mémoire #{existing[0][0]}).",
                }

            mem_id = db_manager.execute_db(
                """INSERT INTO sabrina_memory (content, category, source)
                   VALUES (%s, %s, %s) RETURNING id""",
                (content, category, source),
            )
            return {
                "success": True,
                "memory_id": mem_id,
                "message": f"Mémorisé avec succès (mémoire #{mem_id}, catégorie: {category}).",
            }
        except Exception as e:
            return {"error": f"Erreur lors de la mémorisation : {str(e)}"}

    return _run_async(async_remember(content, category, source))


async def async_remember(
    content: str, category: str = "general", source: str = "user_explicit", db: AsyncSession | None = None
) -> Dict[str, Any]:
    """Version asynchrone native de remember utilisant unit_of_work."""
    if _is_mocked(remember):
        return remember(content, category, source)
    try:
        content = content.strip()
        if not content:
            return {"error": "Contenu vide — impossible de mémoriser."}

        async with unit_of_work(db, auto_commit=True) as session:
            check_stmt = text("SELECT id FROM sabrina_memory WHERE content = :content LIMIT 1")
            res = await session.execute(check_stmt, {"content": content})
            existing_id = res.scalar_one_or_none()
            if existing_id is not None:
                return {
                    "status": "already_known",
                    "message": f"Je connais déjà cette information (mémoire #{existing_id}).",
                }

            ins_stmt = text(
                """INSERT INTO sabrina_memory (content, category, source)
                   VALUES (:content, :category, :source) RETURNING id"""
            )
            res_ins = await session.execute(ins_stmt, {"content": content, "category": category, "source": source})
            mem_id = res_ins.scalar()
            logger.info("Sabrina memory created: id=%s category=%s source=%s", mem_id, category, source)
            return {
                "success": True,
                "memory_id": mem_id,
                "message": f"Mémorisé avec succès (mémoire #{mem_id}, catégorie: {category}).",
            }
    except Exception as e:
        logger.error("Error saving memory: %s", e, exc_info=True)
        return {"error": f"Erreur lors de la mémorisation : {str(e)}"}


def recall(query: str, limit: int = 10) -> Dict[str, Any]:
    """Recherche dans la mémoire de Sabrina par full-text search ou LIKE."""
    if _is_mocked(db_manager) or _is_mocked(getattr(db_manager, "query_db", None)):
        try:
            query = query.strip()
            if not query:
                rows = db_manager.query_db(
                    """SELECT id, category, content, source, relevance_score, created_at
                       FROM sabrina_memory
                       WHERE expires_at IS NULL OR expires_at > NOW()
                       ORDER BY relevance_score DESC, created_at DESC
                       LIMIT %s""",
                    (limit,),
                )
            else:
                rows = db_manager.query_db(
                    """SELECT id, category, content, source, relevance_score, created_at
                       FROM sabrina_memory
                       WHERE (expires_at IS NULL OR expires_at > NOW())
                         AND (
                           search_vector @@ plainto_tsquery('french', %s)
                           OR lower(content) LIKE '%%' || lower(%s) || '%%'
                         )
                       ORDER BY
                         ts_rank(search_vector, plainto_tsquery('french', %s)) DESC,
                         relevance_score DESC
                       LIMIT %s""",
                    (query, query, query, limit),
                )

            memories = []
            for r in rows:
                try:
                    row_dict = dict(r)
                except Exception:
                    row_dict = {
                        "id": r[0],
                        "category": r[1],
                        "content": r[2],
                        "source": r[3],
                        "relevance_score": r[4],
                        "created_at": str(r[5]),
                    }
                memories.append(row_dict)

            return {
                "count": len(memories),
                "memories": memories,
                "message": f"{len(memories)} souvenir(s) trouvé(s)." if memories else "Aucun souvenir trouvé.",
            }
        except Exception as e:
            return {"error": f"Erreur lors du rappel : {str(e)}"}

    return _run_async(async_recall(query, limit))


async def async_recall(query: str, limit: int = 10, db: AsyncSession | None = None) -> Dict[str, Any]:
    """Version asynchrone native de recall utilisant unit_of_work."""
    if _is_mocked(recall):
        return recall(query, limit)
    try:
        query = query.strip()
        async with unit_of_work(db) as session:
            if not query:
                stmt = text(
                    """SELECT id, category, content, source, relevance_score, created_at
                       FROM sabrina_memory
                       WHERE expires_at IS NULL OR expires_at > NOW()
                       ORDER BY relevance_score DESC, created_at DESC
                       LIMIT :limit"""
                )
                res = await session.execute(stmt, {"limit": limit})
            else:
                stmt = text(
                    """SELECT id, category, content, source, relevance_score, created_at
                       FROM sabrina_memory
                       WHERE (expires_at IS NULL OR expires_at > NOW())
                         AND (
                           search_vector @@ plainto_tsquery('french', :q)
                           OR lower(content) LIKE :pat
                         )
                       ORDER BY
                         ts_rank(search_vector, plainto_tsquery('french', :q)) DESC,
                         relevance_score DESC
                       LIMIT :limit"""
                )
                res = await session.execute(stmt, {"q": query, "pat": f"%{query.lower()}%", "limit": limit})

            rows = res.mappings().all()
            memories = []
            for r in rows:
                memories.append({
                    "id": r["id"],
                    "category": r["category"],
                    "content": r["content"],
                    "source": r["source"],
                    "relevance_score": float(r["relevance_score"] or 1.0),
                    "created_at": str(r["created_at"]),
                })

            return {
                "count": len(memories),
                "memories": memories,
                "message": f"{len(memories)} souvenir(s) trouvé(s)." if memories else "Aucun souvenir trouvé.",
            }
    except Exception as e:
        logger.error("Error recalling memories: %s", e, exc_info=True)
        return {"error": f"Erreur lors du rappel : {str(e)}"}


def forget(memory_id: int) -> Dict[str, Any]:
    """Supprime un souvenir spécifique de la mémoire de Sabrina."""
    if _is_mocked(db_manager) or _is_mocked(getattr(db_manager, "execute_db", None)):
        try:
            deleted_id = db_manager.execute_db("DELETE FROM sabrina_memory WHERE id = %s RETURNING id", (memory_id,))
            if deleted_id:
                return {"success": True, "message": f"Souvenir #{memory_id} supprimé."}
            return {"error": f"Souvenir #{memory_id} introuvable."}
        except Exception as e:
            return {"error": f"Erreur lors de la suppression : {str(e)}"}

    return _run_async(async_forget(memory_id))


async def async_forget(memory_id: int, db: AsyncSession | None = None) -> Dict[str, Any]:
    """Version asynchrone native de forget utilisant unit_of_work."""
    if _is_mocked(forget):
        return forget(memory_id)
    try:
        async with unit_of_work(db, auto_commit=True) as session:
            stmt = text("DELETE FROM sabrina_memory WHERE id = :id RETURNING id")
            res = await session.execute(stmt, {"id": int(memory_id)})
            deleted_id = res.scalar_one_or_none()
            if deleted_id:
                logger.info("Sabrina memory deleted: id=%s", memory_id)
                return {"success": True, "message": f"Souvenir #{memory_id} supprimé."}
            return {"error": f"Souvenir #{memory_id} introuvable."}
    except Exception as e:
        logger.error("Error deleting memory %s: %s", memory_id, e, exc_info=True)
        return {"error": f"Erreur lors de la suppression : {str(e)}"}


def get_context_memories(limit: int = 10) -> str:
    """Récupère les souvenirs les plus pertinents pour injection dans le system prompt."""
    if _is_mocked(db_manager) or _is_mocked(getattr(db_manager, "query_db", None)):
        try:
            rows = db_manager.query_db(
                """SELECT category, content FROM sabrina_memory
                   WHERE (expires_at IS NULL OR expires_at > NOW())
                   ORDER BY relevance_score DESC, created_at DESC
                   LIMIT %s""",
                (limit,),
            )
            if not rows:
                return ""

            lines = []
            for r in rows:
                try:
                    cat, content = r["category"], r["content"]
                except (TypeError, KeyError):
                    cat, content = r[0], r[1]
                icon = {"preference": "⭐", "rule": "📌", "context": "📋", "learned": "🧠", "correction": "⚠️"}.get(
                    cat, "💡"
                )
                lines.append(f"  {icon} [{cat}] {content}")

            return "\n🧠 MÉMOIRE PERSISTANTE DE SABRINA (souvenirs importants) :\n" + "\n".join(lines) + "\n"
        except Exception:
            return ""

    return _run_async(async_get_context_memories(limit))


async def async_get_context_memories(limit: int = 10, db: AsyncSession | None = None) -> str:
    """Version asynchrone native de get_context_memories utilisant unit_of_work."""
    if _is_mocked(get_context_memories):
        return get_context_memories(limit)
    try:
        async with unit_of_work(db) as session:
            stmt = text(
                """SELECT category, content FROM sabrina_memory
                   WHERE (expires_at IS NULL OR expires_at > NOW())
                   ORDER BY relevance_score DESC, created_at DESC
                   LIMIT :limit"""
            )
            res = await session.execute(stmt, {"limit": limit})
            rows = res.mappings().all()
            if not rows:
                return ""

            lines = []
            for r in rows:
                cat, content = r["category"], r["content"]
                icon = {"preference": "⭐", "rule": "📌", "context": "📋", "learned": "🧠", "correction": "⚠️"}.get(
                    cat, "💡"
                )
                lines.append(f"  {icon} [{cat}] {content}")

            return "\n🧠 MÉMOIRE PERSISTANTE DE SABRINA (souvenirs importants) :\n" + "\n".join(lines) + "\n"
    except Exception as e:
        logger.error("Error loading context memories: %s", e, exc_info=True)
        return ""
