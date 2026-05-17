from __future__ import annotations
from app.core.db_access import get_db

def next_doc_number(doc_type: str, year: int) -> str:
    """
    doc_type : 'BV' (bon de vente) | 'BA' (bon d'achat)
    Retourne : 'BV-2026-00042'
    Thread-safe et concurrent-safe via PostgreSQL UPSERT atomique avec RETURNING.
    """
    db = get_db()
    key = f"seq_{doc_type}_{year}"
    cur = db.execute("""
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (%s, '1', NOW())
        ON CONFLICT (key) DO UPDATE
        SET value = (app_settings.value::int + 1)::text, updated_at = NOW()
        RETURNING value
    """, (key,))
    row = cur.fetchone()
    seq = int(row["value"])
    cur.close()
    return f"{doc_type}-{year}-{seq:05d}"
