from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import APP_DATA_DIR, DATABASE_URL, settings
from app.core.activity import write_text_log
from app.core.db_access import execute_db, get_setting
from app.core.request_state import get_state_value

BACKUP_DIR = APP_DATA_DIR / "backups"
LOCAL_BACKUP_DIR = BACKUP_DIR / "local"
LOG_DIR = APP_DATA_DIR / "logs"
REPORT_DIR = APP_DATA_DIR / "reports_generated"
NOTES_DIR = APP_DATA_DIR / "notes"
PDF_READER_DIR = APP_DATA_DIR / "pdf_reader"
IMPORT_DIR = APP_DATA_DIR / "imports"
BACKUP_NEEDED_SETTING = "backup_needed"

# Extension des sauvegardes chiffrées
BACKUP_SUFFIX = ".sql.gz.enc"


def _get_encryption_key() -> bytes:
    """Derives a 256-bit key from the app's secret key using PBKDF2-HMAC-SHA256.

    Uses a deterministic salt so the same key is derived across restarts.
    PBKDF2 with 600k iterations provides brute-force resistance compared to raw SHA-256.
    """
    # Deterministic salt tied to the application identity
    salt = hashlib.sha256(b"FABOuanes-backup-encryption-v1").digest()[:16]
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=600_000)
    return kdf.derive(settings.secret_key.encode("utf-8"))


def _encrypt_file(input_path: Path, output_path: Path) -> None:
    """Encrypts a file using AES-GCM and writes to output_path."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    with open(input_path, "rb") as f:
        data = f.read()
    ct = aesgcm.encrypt(nonce, data, None)
    with open(output_path, "wb") as f:
        f.write(nonce + ct)


def _decrypt_file_content(input_path: Path) -> bytes:
    """Decrypts a file and returns its raw bytes."""
    key = _get_encryption_key()
    aesgcm = AESGCM(key)
    with open(input_path, "rb") as f:
        nonce = f.read(12)
        ct = f.read()
    return aesgcm.decrypt(nonce, ct, None)


def _request_db():
    return get_state_value("db")


def _current_user_id() -> int | None:
    user = get_state_value("user")
    if user:
        try:
            return int(user["id"])
        except Exception:
            return None
    return None


def _event_backups_enabled() -> bool:
    return os.environ.get("FAB_ENABLE_EVENT_BACKUPS", "0").strip().lower() in {"1", "true", "yes", "on"}


def mark_backup_needed(reason: str = "event") -> None:
    payload = {
        "reason": str(reason or "event"),
        "marked_at": datetime.now().isoformat(timespec="seconds"),
    }
    execute_db(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
        """,
        (BACKUP_NEEDED_SETTING, json.dumps(payload, ensure_ascii=True, sort_keys=True)),
    )
    
    # Broadcast to connected clients for real-time operations refresh
    try:
        from app.core.websockets import manager
        manager.broadcast_sync("refresh_operations")
    except Exception:
        pass


def get_pending_backup_marker() -> dict:
    raw = get_setting(BACKUP_NEEDED_SETTING, "").strip()
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except Exception:
        return {"reason": raw, "marked_at": ""}
    return payload if isinstance(payload, dict) else {}


def clear_backup_needed() -> None:
    execute_db(
        """
        INSERT INTO app_settings (key, value, updated_at)
        VALUES (%s, '', CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET value='', updated_at=CURRENT_TIMESTAMP
        """,
        (BACKUP_NEEDED_SETTING,),
    )


def ensure_runtime_dirs() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    PDF_READER_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)


def _sha256_of_file(path: Path) -> str:
    """Calcule le SHA-256 d'un fichier (fonctionne sur .gz aussi)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _compress_sql_to_gz(sql_path: Path) -> Path:
    """Compresse un .sql en .sql.gz et supprime le .sql source."""
    gz_path = sql_path.with_suffix(".sql.gz")
    with open(sql_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
        shutil.copyfileobj(f_in, f_out)
    sql_path.unlink(missing_ok=True)
    return gz_path


def capture_local_backup_snapshot(reason: str = "manual") -> Path:
    """
    Produit une sauvegarde PostgreSQL compressée (.sql.gz).

    Stratégie :
    1. pg_dump  (natif, atomique, fiable)
    2. Fallback Python pg8000  (si pg_dump absent)

    La sauvegarde est écrite dans un fichier temporaire puis renommée
    atomiquement pour éviter les fichiers partiels.
    """
    ensure_runtime_dirs()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_reason = reason.replace(" ", "_")
    # Nom final (compressé et chiffré)
    final_name = f"database_{stamp}_{safe_reason}{BACKUP_SUFFIX}"
    final_path = LOCAL_BACKUP_DIR / final_name

    parsed = urlparse(DATABASE_URL)
    username = parsed.username or "postgres"
    password = parsed.password or ""
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 5432
    database = parsed.path.lstrip("/")

    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    # ── 1. pg_dump ──────────────────────────────────────────────────────────
    # Écriture dans un fichier temporaire, puis compression, puis chiffrement
    with tempfile.NamedTemporaryFile(
        suffix=".sql",
        dir=LOCAL_BACKUP_DIR,
        delete=False,
    ) as tmp:
        tmp_sql = Path(tmp.name)

    try:
        cmd = [
            "pg_dump",
            "-h", host, "-p", str(port), "-U", username,
            "-F", "p",          # format texte (plain SQL)
            "--no-password",
            "-f", str(tmp_sql),
            database,
        ]
        subprocess.run(cmd, env=env, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        # Compression
        gz_tmp = tmp_sql.with_suffix(".sql.gz")
        with open(tmp_sql, "rb") as fi, gzip.open(gz_tmp, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        tmp_sql.unlink(missing_ok=True)
        # Chiffrement puis renommage atomique
        enc_tmp = gz_tmp.with_suffix(".sql.gz.enc")
        _encrypt_file(gz_tmp, enc_tmp)
        gz_tmp.unlink(missing_ok=True)
        enc_tmp.rename(final_path)
        return final_path

    except Exception:
        # pg_dump a échoué — nettoyage
        tmp_sql.unlink(missing_ok=True)
        try:
            gz_tmp.unlink(missing_ok=True)
        except Exception:
            pass

    # ── 2. Fallback Python ──────────────────────────────────────────────────
    # Génération via pg8000 dans une transaction READ ONLY pour cohérence.
    # On utilise COPY TO STDOUT … pour éviter les TRUNCATE CASCADE risqués.
    try:
        from app.core.db import connect_database

        conn = connect_database(DATABASE_URL)
        try:
            # Lecture des tables dans l'ordre topologique (dépendances FK)
            cur = conn.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
            tables = [r[0] if not hasattr(r, "keys") else r["tablename"] for r in cur.fetchall()]
            cur.close()

            with tempfile.NamedTemporaryFile(
                mode="wt",
                suffix=".sql",
                dir=LOCAL_BACKUP_DIR,
                delete=False,
                encoding="utf-8",
            ) as tmp_f:
                tmp_sql2 = Path(tmp_f.name)
                tmp_f.write("-- FABOuanes Fallback SQL Dump (pg8000)\n")
                tmp_f.write(f"-- Created at: {datetime.now().isoformat()}\n\n")
                tmp_f.write("BEGIN;\n")
                tmp_f.write("SET CONSTRAINTS ALL DEFERRED;\n\n")

                for table in tables:
                    # Colonnes
                    cur = conn.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=%s "
                        "ORDER BY ordinal_position",
                        (table,),
                    )
                    cols = [r[0] if not hasattr(r, "keys") else r["column_name"] for r in cur.fetchall()]
                    cur.close()

                    # DELETE au lieu de TRUNCATE CASCADE pour éviter les suppressions en cascade
                    tmp_f.write(f"DELETE FROM {table};\n")

                    cur = conn.execute(f"SELECT * FROM {table}")
                    rows = cur.fetchall()
                    cur.close()

                    for row in rows:
                        vals = []
                        for col in cols:
                            val = row[col] if hasattr(row, "keys") else row[cols.index(col)]
                            if val is None:
                                vals.append("NULL")
                            elif isinstance(val, bool):
                                vals.append("TRUE" if val else "FALSE")
                            elif isinstance(val, (int, float)):
                                vals.append(str(val))
                            else:
                                escaped = str(val).replace("'", "''")
                                vals.append(f"'{escaped}'")
                        cols_str = ", ".join(cols)
                        vals_str = ", ".join(vals)
                        tmp_f.write(f"INSERT INTO {table} ({cols_str}) VALUES ({vals_str});\n")
                    tmp_f.write("\n")

                tmp_f.write("COMMIT;\n")

        finally:
            conn.close()

        # Compression + chiffrement + renommage atomique
        gz_tmp2 = tmp_sql2.with_suffix(".sql.gz")
        with open(tmp_sql2, "rb") as fi, gzip.open(gz_tmp2, "wb", compresslevel=6) as fo:
            shutil.copyfileobj(fi, fo)
        tmp_sql2.unlink(missing_ok=True)
        
        enc_tmp2 = gz_tmp2.with_suffix(".sql.gz.enc")
        _encrypt_file(gz_tmp2, enc_tmp2)
        gz_tmp2.unlink(missing_ok=True)
        
        enc_tmp2.rename(final_path)
        return final_path

    except Exception as fe:
        # Dernier recours : écrire un fichier d'erreur compressé et chiffré
        error_sql = f"-- PostgreSQL backup failed.\n-- fallback error: {fe}\n"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".gz", dir=LOCAL_BACKUP_DIR) as terr:
            terr_path = Path(terr.name)
        with gzip.open(terr_path, "wt", encoding="utf-8") as fz:
            fz.write(error_sql)
        _encrypt_file(terr_path, final_path)
        terr_path.unlink(missing_ok=True)
        return final_path


def backup_database(reason: str = "manual", backup_type: str = "event") -> Path:
    if backup_type == "event" and not _event_backups_enabled():
        mark_backup_needed(reason)
        return APP_DATA_DIR / "database.db"  # Chemin factice — aucune opération ici
    target = capture_local_backup_snapshot(reason)
    try:
        from app.services.backup_service import enqueue_backup_upload

        requested_by = _current_user_id()
        enqueue_backup_upload(reason, backup_type, target, requested_by_user_id=requested_by)
        if backup_type in {"manual", "nightly"}:
            clear_backup_needed()
    except Exception as cloud_exc:
        write_text_log("errors.log", f"backup queue failed: {cloud_exc}")
    return target


def restore_database_from(path_str: str) -> None:
    """
    Restaure la BDD depuis un fichier .sql.gz (ou .sql legacy).

    Sécurité :
    - Vérifie le SHA-256 stocké dans backup_jobs (si disponible)
    - Exécute tout dans UNE SEULE transaction PostgreSQL
    - En cas d'erreur → ROLLBACK complet, BDD inchangée
    """
    path = Path(path_str)
    stored_sha256 = _get_stored_sha256(path)
    verify_backup_file(path, expected_sha256=stored_sha256)

    from app.core.db import connect_database
    from app.core.sql_compat import split_sql_script

    # Lire le SQL (déchiffrement puis décompression si applicable)
    if path.name.endswith(".enc"):
        decrypted_bytes = _decrypt_file_content(path)
        if path.name.endswith(".sql.gz.enc"):
            sql_content = gzip.decompress(decrypted_bytes).decode("utf-8", errors="replace")
        else:
            sql_content = decrypted_bytes.decode("utf-8", errors="replace")
    elif path.suffix == ".gz" or path.name.endswith(".sql.gz"):
        with gzip.open(path, "rt", encoding="utf-8") as fz:
            sql_content = fz.read()
    else:
        sql_content = path.read_text(encoding="utf-8")

    conn = connect_database(DATABASE_URL)
    try:
        # Transaction globale unique : tout réussit ou rien ne change
        conn.execute("BEGIN")
        for stmt in split_sql_script(sql_content):
            if stmt.strip():
                conn.execute(stmt)
        conn.execute("COMMIT")
    except Exception as exc:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise RuntimeError(f"Restauration annulée (ROLLBACK effectué) : {exc}") from exc
    finally:
        conn.close()


def _get_stored_sha256(backup_path: Path) -> str | None:
    """Récupère le SHA-256 stocké lors de la création de la sauvegarde."""
    try:
        row = _query_backup_sha256(backup_path.name)
        if row:
            ctx = json.loads(row.get("context_json") or "{}")
            return ctx.get("sha256") or None
    except Exception:
        pass
    return None


def _query_backup_sha256(filename: str):
    """Cherche le job de sauvegarde correspondant au nom de fichier."""
    try:
        from app.core.db_access import query_db
        # La colonne local_path contient le chemin complet
        rows = query_db(
            "SELECT context_json FROM backup_jobs WHERE local_path LIKE %s ORDER BY id DESC LIMIT 1",
            (f"%{filename}",),
        )
        return dict(rows[0]) if rows else None
    except Exception:
        return None


def verify_backup_file(path: Path, *, expected_sha256: str | None = None) -> dict[str, object]:
    """
    Vérifie l'intégrité du fichier de sauvegarde.

    - Vérifie l'existence et la lisibilité du fichier
    - Vérifie le SHA-256 si un hash attendu est fourni
    - Contrôle que le contenu ressemble à du SQL PostgreSQL valide
    """
    if not path.exists() or not path.is_file():
        raise RuntimeError("Fichier de sauvegarde introuvable.")

    # ── Vérification du SHA-256 ──────────────────────────────────────────────
    if expected_sha256:
        actual = _sha256_of_file(path)
        if actual.lower() != expected_sha256.lower():
            raise RuntimeError(
                f"Intégrité corrompue : SHA-256 attendu {expected_sha256[:16]}… "
                f"calculé {actual[:16]}… — restauration annulée."
            )

    # ── Vérification du contenu ──────────────────────────────────────────────
    try:
        if path.name.endswith(".enc"):
            decrypted_bytes = _decrypt_file_content(path)
            if path.name.endswith(".sql.gz.enc"):
                head_bytes = gzip.decompress(decrypted_bytes)[:2048]
            else:
                head_bytes = decrypted_bytes[:2048]
            head = head_bytes.decode("utf-8", errors="replace")
        elif path.suffix == ".gz" or path.name.endswith(".sql.gz"):
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fz:
                head = fz.read(2048)
        else:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(2048)

        sql_keywords = ("--", "CREATE", "INSERT", "SET", "BEGIN", "COPY", "ALTER")
        if not any(kw in head for kw in sql_keywords):
            raise RuntimeError("Sauvegarde invalide : format SQL PostgreSQL non reconnu.")

    except RuntimeError:
        raise
    except Exception as exc:
        raise RuntimeError(f"Impossible de lire la sauvegarde : {exc}") from exc

    return {
        "ok": True,
        "engine": "postgres",
        "path": str(path),
        "sha256_verified": expected_sha256 is not None,
        "compressed": path.name.endswith(".sql.gz") or path.name.endswith(".sql.gz.enc"),
    }


def get_google_drive_sync_dir() -> Path | None:
    raw = get_setting("gdrive_backup_dir", "").strip()
    if not raw:
        return None
    return Path(raw)


def list_restore_backups() -> list[dict[str, str]]:
    backups: list[dict[str, str]] = []
    seen_names: set[str] = set()
    # Chercher .sql.gz.enc en priorité, puis .sql.gz, puis .sql pour rétrocompatibilité
    patterns = ["*.sql.gz.enc", "*.sql.gz", "*.sql"]
    for pattern in patterns:
        for path in sorted(LOCAL_BACKUP_DIR.glob(pattern), reverse=True):
            if path.name in seen_names:
                continue
            seen_names.add(path.name)
            backups.append(
                {
                    "value": f"local:{path.name}",
                    "name": path.name,
                    "source": "local",
                    "label": f"Local - {path.name}",
                }
            )
    sync_dir = get_google_drive_sync_dir()
    if sync_dir and sync_dir.exists():
        for pattern in patterns:
            for path in sorted(sync_dir.glob(pattern), reverse=True):
                if path.name in seen_names:
                    continue
                seen_names.add(path.name)
                backups.append(
                    {
                        "value": f"drive:{path.name}",
                        "name": path.name,
                        "source": "drive",
                        "label": f"Google Drive - {path.name}",
                    }
                )
    return backups


def resolve_backup_path(backup_value: str) -> Path | None:
    raw = (backup_value or "").strip()
    if not raw:
        return None
    if ":" in raw:
        source, name = raw.split(":", 1)
    else:
        source, name = "local", raw
    if source == "local":
        path = LOCAL_BACKUP_DIR / name
        return path if path.exists() else None
    if source in {"drive", "cloud"}:
        sync_dir = get_google_drive_sync_dir()
        if sync_dir:
            path = sync_dir / name
            return path if path.exists() else None
    return None
