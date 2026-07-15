"""
Sabrina Memory — Mémoire persistante de l'assistante IA.

Fournit des fonctions CRUD pour stocker et retrouver des souvenirs (préférences,
contextes, corrections) dans une table PostgreSQL avec recherche vectorielle sémantique et FTS.
"""
from __future__ import annotations

import logging
import json
import httpx
import math
from typing import Dict, Any, List

from app.core.db_helpers import db_manager

logger = logging.getLogger("fabouanes.assistant.memory")


def _ensure_embedding_column():
    """Garantit l'existence de la colonne embedding dans la table sabrina_memory."""
    try:
        db_manager.execute_db("ALTER TABLE sabrina_memory ADD COLUMN IF NOT EXISTS embedding TEXT")
    except Exception as e:
        logger.debug("Failed to ensure embedding column: %s", e)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Calcule la similarité cosinus entre deux vecteurs de nombres réels."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot_product / (norm_a * norm_b)


def get_embedding(text: str) -> list[float] | None:
    """Génère l'embedding du texte en utilisant l'API Gemini ou l'Ollama local."""
    # 1. Essayer Gemini
    try:
        from app.modules.assistant.schema_context import get_gemini_api_key
        api_key = get_gemini_api_key()
        if api_key:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
            headers = {"Content-Type": "application/json"}
            payload = {
                "model": "models/text-embedding-004",
                "content": {"parts": [{"text": text}]}
            }
            with httpx.Client() as client:
                r = client.post(url, json=payload, headers=headers, timeout=10.0)
                if r.status_code == 200:
                    data = r.json()
                    val = data.get("embedding", {}).get("values")
                    if val:
                        return val
    except Exception as e:
        logger.debug("Gemini embedding failed: %s", e)

    # 2. Fallback Ollama local
    try:
        url = "http://127.0.0.1:11434/api/embeddings"
        payload = {
            "model": "qwen2.5:7b",
            "prompt": text
        }
        with httpx.Client() as client:
            r = client.post(url, json=payload, timeout=10.0)
            if r.status_code == 200:
                data = r.json()
                val = data.get("embedding")
                if val:
                    return val
    except Exception as e:
        logger.debug("Ollama embedding failed: %s", e)

    return None


def _row_to_dict(r: Any) -> dict:
    """Convertit de manière robuste une ligne de base de données (CompatRow, tuple brut, dict) en dictionnaire standard."""
    if isinstance(r, dict):
        return r
    if hasattr(r, "keys") and hasattr(r, "__getitem__"):
        try:
            return {k: r[k] for k in r.keys()}
        except Exception:
            pass
    
    # Séquence/Tuple fallback
    row_dict = {}
    cols = ["id", "category", "content", "source", "relevance_score", "created_at", "embedding"]
    for i, col in enumerate(cols):
        if i < len(r):
            val = r[i]
            if col == "created_at" and val is not None:
                val = str(val)
            row_dict[col] = val
        else:
            row_dict[col] = None
    return row_dict


def remember(content: str, category: str = "general", source: str = "user_explicit") -> Dict[str, Any]:
    """Stocke un nouveau souvenir dans la mémoire persistante de Sabrina."""
    try:
        content = content.strip()
        if not content:
            return {"error": "Contenu vide — impossible de mémoriser."}

        _ensure_embedding_column()

        # Vérifier les doublons exacts
        existing = db_manager.query_db(
            "SELECT id FROM sabrina_memory WHERE content = %s LIMIT 1",
            (content,)
        )
        if existing:
            return {"status": "already_known", "message": f"Je connais déjà cette information (mémoire #{existing[0][0]})."}

        # Calculer l'embedding vectoriel
        embedding_val = get_embedding(content)
        embedding_json = json.dumps(embedding_val) if embedding_val else None

        mem_id = db_manager.execute_db(
            """INSERT INTO sabrina_memory (content, category, source, embedding)
               VALUES (%s, %s, %s, %s) RETURNING id""",
            (content, category, source, embedding_json)
        )
        logger.info("Sabrina memory created: id=%s category=%s source=%s with_embedding=%s", mem_id, category, source, bool(embedding_val))
        return {
            "success": True,
            "memory_id": mem_id,
            "message": f"Mémorisé avec succès (mémoire #{mem_id}, catégorie: {category})."
        }
    except Exception as e:
        logger.error("Error saving memory: %s", e, exc_info=True)
        return {"error": f"Erreur lors de la mémorisation : {str(e)}"}


def recall(query: str, limit: int = 10) -> Dict[str, Any]:
    """Recherche dans la mémoire de Sabrina par similarité sémantique (vectorielle) ou FTS/LIKE."""
    try:
        query = query.strip()
        _ensure_embedding_column()

        if not query:
            # Retourner les souvenirs les plus récents
            rows = db_manager.query_db(
                """SELECT id, category, content, source, relevance_score, created_at, embedding
                   FROM sabrina_memory
                   WHERE expires_at IS NULL OR expires_at > NOW()
                   ORDER BY relevance_score DESC, created_at DESC
                   LIMIT %s""",
                (limit,)
            )
            memories = [_row_to_dict(r) for r in rows]
            return {
                "count": len(memories),
                "memories": memories,
                "message": f"{len(memories)} souvenir(s) récent(s) trouvé(s)."
            }

        # 1. Recherche par similarité sémantique vectorielle
        query_emb = get_embedding(query)
        if query_emb:
            # Charger tous les souvenirs qui ont un embedding
            all_rows = db_manager.query_db(
                """SELECT id, category, content, source, relevance_score, created_at, embedding
                   FROM sabrina_memory
                   WHERE (expires_at IS NULL OR expires_at > NOW()) AND embedding IS NOT NULL"""
            )
            scored_memories = []
            for r in all_rows:
                row_dict = _row_to_dict(r)
                emb_str = row_dict.get("embedding")
                if emb_str:
                    try:
                        emb = json.loads(emb_str)
                        if isinstance(emb, list):
                            sim = cosine_similarity(query_emb, emb)
                            # Seuil de pertinence minimum
                            if sim >= 0.35:
                                row_dict["similarity"] = sim
                                scored_memories.append(row_dict)
                    except Exception:
                        pass
            
            if scored_memories:
                # Trier par similarité décroissante
                scored_memories.sort(key=lambda x: x["similarity"], reverse=True)
                memories = scored_memories[:limit]
                return {
                    "count": len(memories),
                    "memories": memories,
                    "message": f"{len(memories)} souvenir(s) trouvé(s) par similarité sémantique."
                }

        # 2. Fallback Recherche full-text en français + LIKE
        rows = db_manager.query_db(
            """SELECT id, category, content, source, relevance_score, created_at, embedding
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
        memories = [_row_to_dict(r) for r in rows]

        return {
            "count": len(memories),
            "memories": memories,
            "message": f"{len(memories)} souvenir(s) trouvé(s) via recherche textuelle."
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
            row_dict = _row_to_dict(r)
            cat, content = row_dict.get("category"), row_dict.get("content")
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
