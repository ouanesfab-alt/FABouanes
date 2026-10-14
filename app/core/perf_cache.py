# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour perf_cache.
Désormais hébergé dans app.infra.perf_cache.
"""

from __future__ import annotations

import sys
from app.infra import perf_cache as _mod

sys.modules[__name__] = _mod
