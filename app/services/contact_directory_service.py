# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour contact_directory_service.
Désormais hébergé dans app.modules.clients.directory_service.
"""

from __future__ import annotations

import sys
from app.modules.clients import directory_service as _mod

sys.modules[__name__] = _mod
