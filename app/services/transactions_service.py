# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour transactions_service.
Désormais hébergé dans app.modules.accounting.service.
"""

from __future__ import annotations

import sys
from app.modules.accounting import service as _mod

sys.modules[__name__] = _mod
