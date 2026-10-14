# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour admin_api.
Désormais hébergé dans app.modules.admin.api.
"""

from __future__ import annotations

import sys
from app.modules.admin import api as _mod

sys.modules[__name__] = _mod
