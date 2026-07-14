from __future__ import annotations

import re
import unicodedata
from typing import List, Dict, Any
from app.web.manual_pages import SPECIFIC_CHAPTER_DATA

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

def search_manual(query: str, limit: int = 3) -> List[Dict[str, Any]]:
    """Search SPECIFIC_CHAPTER_DATA for chapters matching query terms and return matches."""
    query_norm = normalize_text(query)
    query_words = [w for w in query_norm.split() if len(w) > 2]
    if not query_words:
        return []

    scored_chapters = []
    for key, data in SPECIFIC_CHAPTER_DATA.items():
        score = 0
        # Build text to match against
        search_blob = []
        search_blob.append(data.get("fr_title", ""))
        search_blob.append(data.get("ar_title", ""))
        search_blob.extend(data.get("fr_usage", []))
        search_blob.extend(data.get("ar_usage", []))
        search_blob.append(data.get("fr_example", ""))
        search_blob.append(data.get("ar_example", ""))
        
        blob_norm = normalize_text(" ".join(search_blob))
        
        for word in query_words:
            if word in blob_norm:
                score += 1
                # Double score if keyword is in the title
                title_norm = normalize_text(data.get("fr_title", "") + " " + data.get("ar_title", ""))
                if word in title_norm:
                    score += 2
                    
        if score > 0:
            scored_chapters.append((score, key, data))

    # Sort by score descending
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

def get_rag_context(query: str) -> str:
    """Fetch matching manual chapters and format them into a markdown block for LLM context."""
    if not query:
        return ""
    matches = search_manual(query, limit=2)
    if not matches:
        return ""

    context_lines = [
        "\n=== CONTEXTE MANUEL UTILISATEUR ERP (RAG) ===",
        "Voici les sections pertinentes du manuel d'utilisation de l'ERP pour guider votre réponse :",
    ]
    for m in matches:
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
    return "\n".join(context_lines)
