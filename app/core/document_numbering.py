from app.core.db_access import get_db, db_task

@db_task
def next_doc_number(doc_type: str, year: int) -> str:
    """
    doc_type : 'BV' (bon de vente) | 'BA' (bon d'achat)
    Retourne : 'BV-2026-00042'
    Thread-safe et concurrent-safe via PostgreSQL UPSERT atomique avec RETURNING.
    """
    db = get_db()
    key = f"seq_{doc_type}_{year}"
    
    # 1. Self-healing : Déterminer la séquence maximale existant réellement dans les tables de documents
    max_seq = 0
    if doc_type == 'BA':
        cur = db.execute("SELECT doc_number FROM purchase_documents WHERE doc_number LIKE %s", (f"BA-{year}-%",))
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            try:
                seq_num = int(r["doc_number"].split("-")[-1])
                if seq_num > max_seq:
                    max_seq = seq_num
            except Exception:
                pass
    elif doc_type == 'BV':
        cur = db.execute("SELECT doc_number FROM sale_documents WHERE doc_number LIKE %s", (f"BV-{year}-%",))
        rows = cur.fetchall()
        cur.close()
        for r in rows:
            try:
                seq_num = int(r["doc_number"].split("-")[-1])
                if seq_num > max_seq:
                    max_seq = seq_num
            except Exception:
                pass

    # 2. Si un document avec une séquence plus grande existe, on met à jour la séquence dans app_settings
    if max_seq > 0:
        cur = db.execute("SELECT value FROM app_settings WHERE key = %s", (key,))
        cur_val = cur.fetchone()
        cur.close()
        if not cur_val or int(cur_val["value"]) < max_seq:
            cur = db.execute("""
                INSERT INTO app_settings (key, value, updated_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (key) DO UPDATE
                SET value = %s, updated_at = NOW()
            """, (key, str(max_seq), str(max_seq)))
            cur.close()

    # 3. Récupération, incrément atomique et double vérification anti-collision
    while True:
        cur = db.execute("""
            INSERT INTO app_settings (key, value, updated_at)
            VALUES (%s, '1', NOW())
            ON CONFLICT (key) DO UPDATE
            SET value = (app_settings.value::int + 1)::text, updated_at = NOW()
            RETURNING value
        """, (key,))
        row = cur.fetchone()
        cur.close()
        seq = int(row["value"])
        candidate = f"{doc_type}-{year}-{seq:05d}"
        
        # Double vérification finale anti-collision
        if doc_type == 'BA':
            cur = db.execute("SELECT id FROM purchase_documents WHERE doc_number = %s", (candidate,))
            exists = cur.fetchone()
            cur.close()
        else:
            cur = db.execute("SELECT id FROM sale_documents WHERE doc_number = %s", (candidate,))
            exists = cur.fetchone()
            cur.close()
            
        if not exists:
            return candidate
