"""Tests unitaires ciblés pour app/modules/assistant/tool_actions_contacts.py."""
from __future__ import annotations

import pytest
from unittest import mock

from app.modules.assistant.tool_actions_contacts import handle_contacts


@pytest.mark.asyncio
async def test_handle_contacts_modify_delete_not_found():
    mock_session = mock.AsyncMock()
    mock_session.execute.return_value.fetchall.return_value = []
    mock_session.execute.return_value.scalar.return_value = 0
    mock_cm = mock.MagicMock()
    mock_cm.__aenter__ = mock.AsyncMock(return_value=mock_session)
    mock_cm.__aexit__ = mock.AsyncMock(return_value=None)
    mock_session_maker = mock.MagicMock(return_value=mock_cm)

    # modify_client un-found
    with mock.patch("app.modules.clients.service.ClientService.update_client", mock.AsyncMock(return_value=None)):
        res_mod = await handle_contacts("modify_client", {"client_id": 999999, "name": "Nouveau Nom"}, mock_session_maker)
        assert res_mod is not None
        assert "error" in res_mod

    # delete_client un-found
    with mock.patch("app.modules.clients.service.ClientService.delete_client", mock.AsyncMock(return_value=False)):
        res_del = await handle_contacts("delete_client", {"client_id": 999999}, mock_session_maker)
        assert res_del is not None
        assert "error" in res_del

    # modify_supplier un-found
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value=None)):
        res_supp = await handle_contacts("modify_supplier", {"supplier_id": 999999, "name": "Fournisseur Test"}, mock_session_maker)
        assert res_supp is not None
        assert "error" in res_supp

    # delete_supplier un-found
    with mock.patch("app.services.contact_directory_service.get_supplier", mock.AsyncMock(return_value=None)):
        res_del_supp = await handle_contacts("delete_supplier", {"supplier_id": 999999}, mock_session_maker)
        assert res_del_supp is not None
        assert "error" in res_del_supp
