# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour stock_service.
Désormais hébergé dans app.modules.catalog.stock_service.
"""

from __future__ import annotations

import sys
from app.modules.catalog import stock_service as _mod

sys.modules[__name__] = _mod
