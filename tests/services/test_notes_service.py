from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from datetime import datetime

import pytest
from app.core.storage import NOTES_DIR
from app.services.notes_service import (
    notes_file_path,
    read_app_notes,
    write_app_notes,
    list_notes_history,
    read_notes_version,
)


@pytest.fixture(autouse=True)
def clean_notes_directory():
    """Ensure NOTES_DIR is empty before and after each test."""
    import time
    if NOTES_DIR.exists():
        for _ in range(5):
            try:
                shutil.rmtree(NOTES_DIR)
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            shutil.rmtree(NOTES_DIR, ignore_errors=True)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    yield
    if NOTES_DIR.exists():
        for _ in range(5):
            try:
                shutil.rmtree(NOTES_DIR)
                break
            except PermissionError:
                time.sleep(0.1)
        else:
            shutil.rmtree(NOTES_DIR, ignore_errors=True)


def test_notes_file_path():
    path = notes_file_path()
    assert isinstance(path, Path)
    assert path.name == "bloc_note.txt"
    assert path.parent == NOTES_DIR


def test_read_empty_notes():
    assert read_app_notes() == ""


def test_write_and_read_notes():
    content = "Hello, world! This is a test note."
    write_app_notes(content)
    assert read_app_notes() == content


def test_write_notes_creates_history():
    # Write first time
    write_app_notes("Version 1")
    assert read_app_notes() == "Version 1"
    assert len(list(NOTES_DIR.glob("history_*.txt"))) == 0

    # Write second time with different content should create a history file of Version 1
    write_app_notes("Version 2")
    assert read_app_notes() == "Version 2"
    
    history_files = list(NOTES_DIR.glob("history_*.txt"))
    assert len(history_files) == 1
    archived_content = history_files[0].read_text(encoding="utf-8")
    assert archived_content == "Version 1"


def test_write_same_notes_does_not_create_history():
    write_app_notes("Version 1")
    write_app_notes("Version 1")
    assert len(list(NOTES_DIR.glob("history_*.txt"))) == 0


def test_list_notes_history_and_read_version():
    write_app_notes("Version 1")
    # Small pause to ensure unique timestamps in filename if generated quickly
    # but the service uses datetime.now().strftime("%Y%m%d_%H%M%S").
    # To mock different timestamps, we can write, wait 1s, or manually create files.
    # Let's write another version
    time.sleep(1.1)
    write_app_notes("Version 2")
    
    history = list_notes_history()
    assert len(history) == 1
    assert "filename" in history[0]
    assert "label" in history[0]
    
    filename = history[0]["filename"]
    content = read_notes_version(filename)
    assert content == "Version 1"


def test_notes_history_rotation_limit():
    # Populate notes 25 times to check rotation limits (max 20 versions)
    for i in range(25):
        write_app_notes(f"Content {i}")
        # Need to wait 1 second between writes to avoid sharing the same filename timestamp
        # or we can mock/manually write files to speed up the test.
        # Let's manually write 25 files in NOTES_DIR simulating history
        # because waiting 25 seconds in a unit test is too slow.
    
    # Clean first
    if NOTES_DIR.exists():
        shutil.rmtree(NOTES_DIR)
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Write 25 mock history files
    for i in range(25):
        # Format: history_YYYYMMDD_HHMMSS.txt
        stamp = f"20260522_1200{i:02d}"
        path = NOTES_DIR / f"history_{stamp}.txt"
        path.write_text(f"Mock Content {i}", encoding="utf-8")
        
    # Write to bloc_note.txt to trigger rotation
    notes_file_path().write_text("Current Content", encoding="utf-8")
    
    # write_app_notes with new content to trigger historical archive and rotation
    write_app_notes("New Current Content")
    
    # Check that we only have max 20 history files remaining
    history_files = sorted(NOTES_DIR.glob("history_*.txt"))
    assert len(history_files) == 20
    
    # Verify that the older files (like 120000, 120001, etc.) were deleted
    # The remaining files should be the 20 most recent
    labels = [f.name for f in history_files]
    assert "history_20260522_120000.txt" not in labels
    assert "history_20260522_120024.txt" in labels


def test_read_notes_version_traversal_protection():
    write_app_notes("Current")
    # Create a history file
    write_app_notes("Current 2")
    
    history = list_notes_history()
    assert len(history) == 1
    filename = history[0]["filename"]
    
    # Normal read
    assert read_notes_version(filename) == "Current"
    
    # Traversal read attempts
    assert read_notes_version(f"../notes/{filename}") == "Current"  # replacement strips ../
    assert read_notes_version(f"..\\notes\\{filename}") == "Current" # replacement strips .. and \
    
    # Non-existent or invalid suffixes should return empty string
    assert read_notes_version("nonexistent.txt") == ""
    assert read_notes_version("bloc_note.html") == ""
