from __future__ import annotations

import tempfile
import time
import os
from pathlib import Path
from unittest.mock import patch
import pytest

from app.services.backup_service import (
    _calculate_sha256,
    _apply_retention_to_directory,
    enqueue_backup_upload,
    get_backup_settings,
    save_backup_configuration,
    run_pending_backup_jobs,
    enqueue_backup_snapshot,
    list_backup_jobs,
    _purge_old_logs,
)
from app.core.db_access import query_db, execute_db


def test_calculate_sha256():
    with tempfile.NamedTemporaryFile(delete=False) as f:
        f.write(b"test backup data")
        temp_path = Path(f.name)
    try:
        checksum = _calculate_sha256(temp_path)
        import hashlib
        expected = hashlib.sha256(b"test backup data").hexdigest()
        assert checksum == expected
    finally:
        temp_path.unlink()


@pytest.mark.asyncio
async def test_backup_configuration():
    payload = {
        "gdrive_backup_dir": "/tmp/test_gdrive",
        "backup_snapshot_time": "04:30",
        "backup_local_retention": 15,
        "backup_event_retention": 45,
    }
    await save_backup_configuration(payload)
    
    settings = await get_backup_settings()
    assert settings["gdrive_backup_dir"] == "/tmp/test_gdrive"
    assert settings["backup_snapshot_time"] == "04:30"
    assert settings["backup_local_retention"] == 15
    assert settings["backup_event_retention"] == 45


@pytest.mark.asyncio
async def test_apply_retention_to_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        files = []
        for i in range(5):
            p = dir_path / f"backup_{i}.sql.gz"
            p.write_bytes(b"data")
            os.utime(p, (time.time() - (10 - i) * 60, time.time() - (10 - i) * 60))
            files.append(p)
        
        with patch("app.services.backup_service._retention_limit_for_type", return_value=3):
            await _apply_retention_to_directory(dir_path, "event")
            
        remaining = list(dir_path.glob("*.sql.gz"))
        assert len(remaining) == 3
        remaining_names = {p.name for p in remaining}
        assert "backup_0.sql.gz" not in remaining_names
        assert "backup_1.sql.gz" not in remaining_names
        assert "backup_2.sql.gz" in remaining_names
        assert "backup_3.sql.gz" in remaining_names
        assert "backup_4.sql.gz" in remaining_names


@pytest.mark.asyncio
async def test_backup_jobs_queuing_and_execution():
    execute_db("DELETE FROM backup_jobs")
    execute_db("DELETE FROM backup_runs")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".sql") as tmp:
        tmp.write(b"CREATE TABLE test (id int);")
        tmp_path = Path(tmp.name)
        
    try:
        job_id = await enqueue_backup_upload(
            reason="test manually",
            backup_type="manual",
            local_path=tmp_path
        )
        assert job_id > 0
        
        jobs_list = await list_backup_jobs(limit=10)
        assert len(jobs_list) >= 1
        
        processed = await run_pending_backup_jobs(limit=1)
        assert processed == 1
        
        rows = query_db("SELECT status, cloud_file_name FROM backup_jobs WHERE id = %s", (job_id,))
        assert rows[0]["status"] == "success"
        
        runs = query_db("SELECT status FROM backup_runs WHERE job_id = %s", (job_id,))
        assert len(runs) == 1
        assert runs[0]["status"] == "success"
        
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_enqueue_backup_snapshot():
    execute_db("DELETE FROM backup_jobs")
    job_id = await enqueue_backup_snapshot("Nightly Auto", "nightly")
    assert job_id > 0
    job = query_db("SELECT * FROM backup_jobs WHERE id = %s", (job_id,), one=True)
    assert job["reason"] == "Nightly Auto"
    assert job["backup_type"] == "nightly"
    assert job["status"] == "pending"


@pytest.mark.asyncio
async def test_purge_old_logs():
    await _purge_old_logs()
