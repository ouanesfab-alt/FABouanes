"""
Sabrina Memory — Mémoire persistante de l'assistante IA.

Fournit des fonctions CRUD pour stocker et retrouver des souvenirs (préférences,
contextes, corrections) dans une table PostgreSQL avec recherche full-text.
"""
from __future__ import annotations

import logging
from typing import Dict, Any

from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant.memory")


def remember(content: str, category: str = "general", source: str = "user_explicit") -> Dict[str, Any]:
    """Stocke un nouveau souvenir dans la mémoire persistante de Sabrina."""
    try:
        content = content.strip()
        if not content:
            return {"error": "Contenu vide — impossible de mémoriser."}

        # Vérifier les doublons exacts
        existing = db_manager.query_db(
            "SELECT id FROM sabrina_memory WHERE content = %s LIMIT 1",
            (content,)
        )
        if existing:
            return {"status": "already_known", "message": f"Je connais déjà cette information (mémoire #{existing[0][0]})."}

        mem_id = db_manager.execute_db(
            """INSERT INTO sabrina_memory (content, category, source)
               VALUES (%s, %s, %s) RETURNING id""",
            (content, category, source)
        )
        logger.info("Sabrina memory created: id=%s category=%s source=%s", mem_id, category, source)
        return {
            "success": True,
            "memory_id": mem_id,
            "message": f"Mémorisé avec succès (mémoire #{mem_id}, catégorie: {category})."
        }
    except Exception as e:
        logger.error("Error saving memory: %s", e, exc_info=True)
        return {"error": f"Erreur lors de la mémorisation : {str(e)}"}


def recall(query: str, limit: int = 10) -> Dict[str, Any]:
    """Recherche dans la mémoire de Sabrina par full-text search ou LIKE."""
    try:
        query = query.strip()
        if not query:
            # Retourner les souvenirs les plus récents
            rows = db_manager.query_db(
                """SELECT id, category, content, source, relevance_score, created_at
                   FROM sabrina_memory
                   WHERE expires_at IS NULL OR expires_at > NOW()
                   ORDER BY relevance_score DESC, created_at DESC
                   LIMIT %s""",
                (limit,)
            )
        else:
            # Recherche full-text en français + fallback LIKE
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
                (query, query, query, limit)
            )

        memories = []
        for r in rows:
            try:
                row_dict = dict(r)
            except Exception:
                row_dict = {
                    "id": r[0], "category": r[1], "content": r[2],
                    "source": r[3], "relevance_score": r[4], "created_at": str(r[5])
                }
            memories.append(row_dict)

        return {
            "count": len(memories),
            "memories": memories,
            "message": f"{len(memories)} souvenir(s) trouvé(s)." if memories else "Aucun souvenir trouvé."
        }
    except Exception as e:
        logger.error("Error recalling memories: %s", e, exc_info=True)
        return {"error": f"Erreur lors du rappel : {str(e)}"}


def forget(memory_id: int) -> Dict[str, Any]:
    """Supprime un souvenir spécifique de la mémoire de Sabrina."""
    try:
        deleted_id = db_manager.execute_db(
            "DELETE FROM sabrina_memory WHERE id = %s RETURNING id", (memory_id,)
        )
        if deleted_id:
            logger.info("Sabrina memory deleted: id=%s", memory_id)
            return {"success": True, "message": f"Souvenir #{memory_id} supprimé."}
        return {"error": f"Souvenir #{memory_id} introuvable."}
    except Exception as e:
        logger.error("Error deleting memory %s: %s", memory_id, e, exc_info=True)
        return {"error": f"Erreur lors de la suppression : {str(e)}"}


def get_context_memories(limit: int = 10) -> str:
    """
    Récupère les souvenirs les plus pertinents pour injection dans le system prompt.
    Retourne un texte formaté prêt à être injecté.
    """
    try:
        rows = db_manager.query_db(
            """SELECT category, content FROM sabrina_memory
               WHERE (expires_at IS NULL OR expires_at > NOW())
               ORDER BY relevance_score DESC, created_at DESC
               LIMIT %s""",
            (limit,)
        )
        if not rows:
            return ""

        lines = []
        for r in rows:
            try:
                cat, content = r["category"], r["content"]
            except (TypeError, KeyError):
                cat, content = r[0], r[1]
            icon = {"preference": "⭐", "rule": "📌", "context": "📋", "learned": "🧠", "correction": "⚠️"}.get(cat, "💡")
            lines.append(f"  {icon} [{cat}] {content}")

        return (
            "\n🧠 MÉMOIRE PERSISTANTE DE SABRINA (souvenirs importants) :\n"
            + "\n".join(lines)
            + "\n"
        )
    except Exception as e:
        logger.error("Error loading context memories: %s", e, exc_info=True)
        return ""
