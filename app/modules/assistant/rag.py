from __future__ import annotations

import os
import re
import json
import unicodedata
from pathlib import Path
from typing import List, Dict, Any
from pypdf import PdfReader

from app.web.manual_pages import SPECIFIC_CHAPTER_DATA
from app.core.runtime_paths import paths

INDEX_FILE = paths.pdf_reader_dir / "index_rag.json"

def normalize_text(text: str) -> str:
    """Normalize text for simple keyword matching: lowercase, strip accents, remove non-alphanumeric."""
    text = text.lower()
    # Normalize accents
    text = "".join(
        c for c in unicodedata.normalize("NFD", text)
        if unicodedata.category(c) != "Mn"
    )
    # Only keep letters, digits, and spaces
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())

# Domain synonyms mapping for intelligent search matching
SYNONYM_MAP: dict[str, list[str]] = {
    "facture": ["vente", "operation", "bon", "facturation", "client"],
    "vente": ["facture", "operation", "credit", "cash", "client"],
    "client": ["contact", "creance", "compte", "clientele"],
    "fournisseur": ["achat", "contact", "dette", "approvisionnement"],
    "stock": ["produit", "matiere", "inventaire", "catalogue", "entrepot"],
    "produit": ["stock", "article", "catalogue", "marchandise"],
    "recette": ["production", "composition", "formule", "batch"],
    "production": ["recette", "fabrique", "transformation", "batch"],
    "depense": ["charge", "frais", "caisse", "sortie"],
    "rapport": ["statistique", "bilan", "kpi", "chiffre"],
}

def search_manual(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search SPECIFIC_CHAPTER_DATA for chapters matching query terms and synonyms with BM25 term weighting."""
    query_norm = normalize_text(query)
    base_words = [w for w in query_norm.split() if len(w) > 2]
    if not base_words:
        return []

    # Expand words with domain synonyms
    query_words = set(base_words)
    for word in base_words:
        if word in SYNONYM_MAP:
            query_words.update(SYNONYM_MAP[word])

    scored_chapters = []
    for key, data in SPECIFIC_CHAPTER_DATA.items():
        score = 0.0
        search_blob = []
        search_blob.append(data.get("fr_title", ""))
        search_blob.append(data.get("ar_title", ""))
        search_blob.extend(data.get("fr_usage", []))
        search_blob.extend(data.get("ar_usage", []))
        search_blob.append(data.get("fr_example", ""))
        search_blob.append(data.get("ar_example", ""))

        blob_norm = normalize_text(" ".join(search_blob))
        title_norm = normalize_text(data.get("fr_title", "") + " " + data.get("ar_title", ""))

        for word in query_words:
            if word in blob_norm:
                # Direct word matches carry higher weight than synonym matches
                weight = 3.0 if word in base_words else 1.5
                score += weight
                if word in title_norm:
                    score += weight * 2.0

        if score > 0:
            scored_chapters.append((score, key, data))

    scored_chapters.sort(key=lambda x: x[0], reverse=True)


    results = []
    for score, key, data in scored_chapters[:limit]:
        results.append({
            "chapter_id": key,
            "fr_title": data.get("fr_title"),
            "ar_title": data.get("ar_title"),
            "fr_usage": data.get("fr_usage", []),
            "ar_usage": data.get("ar_usage", []),
            "fr_example": data.get("fr_example"),
            "ar_example": data.get("ar_example")
        })
    return results


async def search_vector_manual(query: str, api_key: str, limit: int = 2) -> List[Dict[str, Any]]:
    """Recherche vectorielle sémantique dans les chapitres du manuel utilisateur indexés."""
    emb = await get_embedding(query, api_key)
    if not emb:
        return []

    from app.core.db_helpers import query_db
    has_vector = False
    try:
        row = query_db("SELECT 1 FROM pg_extension WHERE extname = 'vector'", one=True)
        has_vector = bool(row)
    except Exception:
        pass

    results = []
    if has_vector:
        emb_str = f"[{','.join(str(x) for x in emb)}]"
        rows = query_db(
            """SELECT item_id, 1 - (embedding <=> %s::vector) AS score
               FROM catalog_embeddings
               WHERE item_kind = 'manual'
               ORDER BY embedding <=> %s::vector ASC
               LIMIT %s""",
            (emb_str, emb_str, limit)
        )
        if rows:
            for r in rows:
                try:
                    m_id = r["item_id"]
                except (TypeError, KeyError):
                    m_id = r[0]
                major = m_id // 100
                minor = m_id % 100
                key = f"{major}-{minor}"
                data = SPECIFIC_CHAPTER_DATA.get(key)
                if data:
                    results.append({
                        "chapter_id": key,
                        "fr_title": data.get("fr_title"),
                        "ar_title": data.get("ar_title"),
                        "fr_usage": data.get("fr_usage", []),
                        "ar_usage": data.get("ar_usage", []),
                        "fr_example": data.get("fr_example"),
                        "ar_example": data.get("ar_example")
                    })
    return results


def get_pdf_text_chunks(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract text from a PDF file and return chunks with page numbers."""
    chunks = []
    try:
        reader = PdfReader(str(pdf_path))
        for page_idx, page in enumerate(reader.pages):
            text = page.extract_text()
            if not text:
                continue
            # Split text by paragraphs or lines to avoid huge chunks
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for p_idx, para in enumerate(paragraphs):
                if len(para) < 20:
                    continue
                chunks.append({
                    "text": para,
                    "page": page_idx + 1,
                    "para_idx": p_idx
                })
    except Exception:
        pass
    return chunks

def update_pdf_index() -> Dict[str, Any]:
    """Sync the index_rag.json file with the actual PDFs present in the pdf_reader directory."""
    paths.pdf_reader_dir.mkdir(parents=True, exist_ok=True)

    index_data = {}
    if INDEX_FILE.exists():
        try:
            with INDEX_FILE.open("r", encoding="utf-8") as f:
                index_data = json.load(f)
        except Exception:
            index_data = {}

    pdf_files = list(paths.pdf_reader_dir.glob("*.pdf"))
    pdf_names = {f.name for f in pdf_files}

    # Remove deleted PDFs from index
    keys_to_delete = [k for k in index_data if k not in pdf_names]
    for k in keys_to_delete:
        del index_data[k]

    # Index new or modified PDFs
    updated = False
    for f in pdf_files:
        try:
            mtime = os.path.getmtime(f)
        except Exception:
            mtime = 0.0

        if f.name not in index_data or index_data[f.name].get("mtime") != mtime:
            chunks = get_pdf_text_chunks(f)
            index_data[f.name] = {
                "mtime": mtime,
                "chunks": chunks
            }
            updated = True

    if updated or keys_to_delete:
        try:
            with INDEX_FILE.open("w", encoding="utf-8") as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    return index_data

def search_user_documents(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search through indexed user documents (PDFs) and return top matches."""
    query_norm = normalize_text(query)
    query_words = [w for w in query_norm.split() if len(w) > 2]
    if not query_words:
        return []

    index_data = update_pdf_index()
    scored_chunks = []

    for doc_name, doc_info in index_data.items():
        chunks = doc_info.get("chunks", [])
        for chunk in chunks:
            text = chunk.get("text", "")
            text_norm = normalize_text(text)
            score = 0
            for word in query_words:
                if word in text_norm:
                    score += 1
            if score > 0:
                scored_chunks.append({
                    "score": score,
                    "doc_name": doc_name,
                    "page": chunk.get("page", 1),
                    "text": text
                })

    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks[:limit]

import time
_embedding_cache: dict[str, tuple[float, List[float]]] = {}
CACHE_EXPIRY = 900.0  # 15 minutes


async def get_embedding(text: str, api_key: str) -> List[float] | None:
    """Fetch text embedding from Gemini API with retry, exponential backoff, and in-memory caching."""
    # 1. Clean expired cache entries
    now = time.time()
    expired_keys = [k for k, v in _embedding_cache.items() if now - v[0] > CACHE_EXPIRY]
    for k in expired_keys:
        _embedding_cache.pop(k, None)

    # 2. Check cache
    cached = _embedding_cache.get(text)
    if cached:
        return cached[1]

    import httpx
    import asyncio
    url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"

    headers = {"Content-Type": "application/json"}

    if api_key.startswith("AIzaSy") or api_key.startswith("AQ"):
        url = f"{url}?key={api_key}"
    else:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": "models/text-embedding-004",
        "content": {"parts": [{"text": text}]}
    }

    retries = 3
    backoff = 1.0
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(url, json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                vals = data["embedding"]["values"]
                _embedding_cache[text] = (time.time(), vals)
                return vals
        except Exception as e:
            import logging
            logger = logging.getLogger("fabouanes.rag")
            if attempt == retries - 1:
                logger.warning("Failed to fetch embedding after %d attempts: %s", retries, e)
                return None
            logger.info("Embedding fetch failed (attempt %d/%d), retrying in %.1fs...", attempt + 1, retries, backoff)
            await asyncio.sleep(backoff)
            backoff *= 2.0
    return None


async def search_vector_catalog(query: str, api_key: str, limit: int = 5) -> List[Dict[str, Any]]:
    if not api_key:
        return []

    from app.core.db_helpers import query_db
    has_vector = False
    try:
        row = query_db("SELECT 1 FROM pg_extension WHERE extname = 'vector'", one=True)
        has_vector = bool(row)
    except Exception:
        pass

    emb = await get_embedding(query, api_key)
    if not emb or len(emb) != 1536:
        return []

    results = []
    if has_vector:
        emb_str = f"[{','.join(str(x) for x in emb)}]"
        rows = query_db(
            """
            SELECT item_kind, item_id, text_content, (embedding <=> %s::vector) AS distance
            FROM catalog_embeddings
            ORDER BY distance ASC
            LIMIT %s
            """,
            (emb_str, limit)
        )
        for r in rows or []:
            score = 1.0 - float(r["distance"] or 0)
            # Enforce similarity threshold of 0.5
            if score >= 0.5:
                results.append({
                    "kind": r["item_kind"],
                    "id": r["item_id"],
                    "text": r["text_content"],
                    "score": score
                })
    else:
        rows = query_db(
            "SELECT item_kind, item_id, text_content, embedding FROM catalog_embeddings"
        )
        scored = []
        for r in rows or []:
            try:
                item_emb = json.loads(r["embedding"])
                if len(item_emb) == len(emb):
                    import math
                    dot = sum(x * y for x, y in zip(emb, item_emb))
                    norm1 = math.sqrt(sum(x*x for x in emb))
                    norm2 = math.sqrt(sum(y*y for y in item_emb))
                    sim = dot / (norm1 * norm2) if norm1 and norm2 else 0
                    # Enforce similarity threshold of 0.5
                    if sim >= 0.5:
                        scored.append((sim, r))
            except Exception:
                pass
        scored.sort(key=lambda x: x[0], reverse=True)
        for sim, r in scored[:limit]:
            results.append({
                "kind": r["item_kind"],
                "id": r["item_id"],
                "text": r["text_content"],
                "score": sim
            })

    return results


def get_rag_context(query: str) -> str:
    """Fetch matching manual chapters, user documents, and catalog items, and format them into a markdown block."""
    if not query:
        return ""

    manual_matches = []
    catalog_matches = []
    doc_matches = search_user_documents(query, limit=3)

    try:
        from app.modules.assistant.schema_context import get_gemini_api_key
        api_key = get_gemini_api_key()
        if api_key:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            def run_async(coro):
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
            with ThreadPoolExecutor() as executor:
                # Search manual sémantiquement
                future_m = executor.submit(run_async, search_vector_manual(query, api_key, limit=2))
                manual_matches = future_m.result()
                # Search catalog sémantiquement
                future_c = executor.submit(run_async, search_vector_catalog(query, api_key, limit=3))
                catalog_matches = future_c.result()
    except Exception as e:
        import logging
        logging.getLogger("fabouanes.rag").debug("Semantic RAG search failed: %s", e)

    # Fallback to BM25 if vector search returned nothing or was disabled
    if not manual_matches:
        manual_matches = search_manual(query, limit=2)


    if not manual_matches and not doc_matches and not catalog_matches:
        return ""

    context_lines = []

    if catalog_matches:
        context_lines.append("\n=== CONTEXTE CATALOGUE PRODUITS (RAG VECTORIEL SEMANTIQUE) ===")
        context_lines.append("Voici les articles du catalogue sémantiquement proches de la demande :")
        for c in catalog_matches:
            kind_str = "Produit Fini" if c["kind"] == "finished" else "Matière Première"
            context_lines.append(f"- [{kind_str} ID={c['id']}] {c['text']} (similarité: {c['score']:.2f})")
        context_lines.append("================================================================\n")

    if manual_matches:
        context_lines.append("\n=== CONTEXTE MANUEL UTILISATEUR ERP (RAG) ===")
        context_lines.append("Voici les sections pertinentes du manuel d'utilisation de l'ERP pour guider votre réponse :")
        for m in manual_matches:
            context_lines.append(f"\nSection {m['chapter_id']}: {m['fr_title']} / {m['ar_title']}")
            context_lines.append("Instructions d'utilisation (Français) :")
            for step in m["fr_usage"]:
                context_lines.append(f"- {step}")
            if m["fr_example"]:
                context_lines.append(f"Exemple : {m['fr_example']}")

            context_lines.append("Instructions d'utilisation (Arabe) :")
            for step in m["ar_usage"]:
                context_lines.append(f"- {step}")
            if m["ar_example"]:
                context_lines.append(f"Exemple : {m['ar_example']}")
        context_lines.append("=============================================\n")

    if doc_matches:
        context_lines.append("\n=== CONTEXTE DOCUMENTS UTILISATEURS IMPORTÉS (RAG) ===")
        context_lines.append("Voici les passages pertinents extraits des documents PDF importés par l'utilisateur :")
        for d in doc_matches:
            context_lines.append(f"\nDocument : {d['doc_name']} (Page {d['page']})")
            context_lines.append(f"Extrait : {d['text']}")
        context_lines.append("======================================================\n")

    return "\n".join(context_lines)
