# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour activity_service.
Désormais hébergé dans app.modules.admin.activity_service.
"""

from __future__ import annotations

import sys
from app.modules.admin import activity_service as _mod

sys.modules[__name__] = _mod
