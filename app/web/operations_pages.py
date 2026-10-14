# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour operations_pages.
Désormais hébergé dans app.modules.accounting.web.
"""

from __future__ import annotations

import sys
from app.modules.accounting import web as _mod

sys.modules[__name__] = _mod
