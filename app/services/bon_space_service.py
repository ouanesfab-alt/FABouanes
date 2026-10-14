# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour bon_space_service.
Désormais hébergé dans app.modules.reports.bon_space_service.
"""

from __future__ import annotations

import sys
from app.modules.reports import bon_space_service as _mod

sys.modules[__name__] = _mod
