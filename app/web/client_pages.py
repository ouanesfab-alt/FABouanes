# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour client_pages.
Désormais hébergé dans app.modules.clients.client_pages.
"""

from __future__ import annotations

import sys
from app.modules.clients import client_pages as _mod

sys.modules[__name__] = _mod
