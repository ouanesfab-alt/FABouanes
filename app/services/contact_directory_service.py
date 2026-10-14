# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour contact_directory_service.
Toutes les fonctions sont désormais hébergées dans app.modules.clients.directory_service.
"""

from __future__ import annotations

from app.modules.clients.directory_service import (
    _build_contacts_context,
    _build_supplier_detail_context,
    _create_supplier_from_form_impl,
    _delete_supplier_by_id_impl,
    _get_supplier_impl,
    _has_supplier_operations_impl,
    _update_supplier_from_form_impl,
    contacts_context,
    create_supplier_from_form,
    delete_supplier_by_id,
    get_supplier,
    get_supplier_detail_context,
    has_supplier_operations,
    update_supplier_from_form,
)

__all__ = [
    "contacts_context",
    "_build_contacts_context",
    "create_supplier_from_form",
    "_create_supplier_from_form_impl",
    "get_supplier",
    "_get_supplier_impl",
    "update_supplier_from_form",
    "_update_supplier_from_form_impl",
    "has_supplier_operations",
    "_has_supplier_operations_impl",
    "delete_supplier_by_id",
    "_delete_supplier_by_id_impl",
    "get_supplier_detail_context",
    "_build_supplier_detail_context",
]
