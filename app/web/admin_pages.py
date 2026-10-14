# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour admin_pages.
Désormais hébergé dans app.modules.admin.web.
"""

from __future__ import annotations

import sys
from app.modules.admin import web as _mod

sys.modules[__name__] = _mod
