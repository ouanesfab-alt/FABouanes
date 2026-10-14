# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour backup_service.
Désormais hébergé dans app.modules.admin.backup_service.
"""

from __future__ import annotations

import sys
from app.modules.admin import backup_service as _mod

sys.modules[__name__] = _mod
