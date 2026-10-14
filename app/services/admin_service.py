# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour admin_service.
Désormais hébergé dans app.modules.admin.service.
"""

from __future__ import annotations

import sys
from app.modules.admin import service as _mod

sys.modules[__name__] = _mod
