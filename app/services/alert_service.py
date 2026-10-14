# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour alert_service.
Désormais hébergé dans app.modules.admin.alert_service.
"""

from __future__ import annotations

import sys
from app.modules.admin import alert_service as _mod

sys.modules[__name__] = _mod
