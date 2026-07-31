"""Tests unitaires pour les sous-fonctions refactorées de assistant_chat (lot C4)."""
from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock
from app.modules.assistant.web import (
    _resolve_api_key,
    _parse_audio_message,
    _handle_file_attachment
)


def test_parse_audio_message_normal_text():
    text, audio = _parse_audio_message("Bonjour Sabrina")
    assert text == "Bonjour Sabrina"
    assert audio is None


def test_parse_audio_message_audio_format_with_transcript():
    raw = "[AUDIO:data:audio/webm;base64,QUJDRA==|Voici ma note vocale]"
    text, audio = _parse_audio_message(raw)
    assert text == "Voici ma note vocale"
    assert audio == {"mimeType": "audio/webm", "data": "QUJDRA=="}


def test_parse_audio_message_audio_format_no_transcript():
    raw = "[AUDIO:data:audio/webm;base64,QUJDRA==|]"
    text, audio = _parse_audio_message(raw)
    assert "Transcris ce message audio" in text
    assert audio == {"mimeType": "audio/webm", "data": "QUJDRA=="}


def test_resolve_api_key_masked_fallback():
    with patch("app.modules.assistant.web.get_gemini_api_key", return_value="KEY_FALLBACK"):
        key = _resolve_api_key("••••••••")
        assert key == "KEY_FALLBACK"


def test_resolve_api_key_explicit_valid():
    with patch("app.modules.assistant.web.db_manager.get_setting", return_value=""), \
         patch("app.modules.assistant.web.get_encryption_key", return_value="secret"):
        key = _resolve_api_key("MY_EXPLICIT_KEY")
        assert key == "MY_EXPLICIT_KEY"


def test_handle_file_attachment_none():
    msg = {"parts": [{"text": "Hello"}]}
    _handle_file_attachment(None, msg)
    assert len(msg["parts"]) == 1


def test_handle_file_attachment_generic_file():
    msg = {"parts": [{"text": "Hello"}]}
    file_obj = {"mime_type": "image/png", "data": "BASE64IMAGE", "name": "pic.png"}
    _handle_file_attachment(file_obj, msg)
    assert len(msg["parts"]) == 2
    assert msg["parts"][1]["inlineData"]["mimeType"] == "image/png"
