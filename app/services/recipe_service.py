# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour recipe_service.
Désormais hébergé dans app.modules.production.service.
"""

from __future__ import annotations

import sys
from app.modules.production import service as _mod

sys.modules[__name__] = _mod
