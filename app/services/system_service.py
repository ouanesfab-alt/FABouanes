# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour system_service.
Désormais hébergé dans app.modules.admin.system_service.
"""

from __future__ import annotations

import sys
from app.modules.admin import system_service as _mod

sys.modules[__name__] = _mod
