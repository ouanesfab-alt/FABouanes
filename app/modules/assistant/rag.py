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

def get_rag_context(query: str) -> str:
    """Fetch matching manual chapters and user documents, and format them into a markdown block."""
    if not query:
        return ""
        
    manual_matches = search_manual(query, limit=2)
    doc_matches = search_user_documents(query, limit=3)
    
    if not manual_matches and not doc_matches:
        return ""
        
    context_lines = []
    
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
