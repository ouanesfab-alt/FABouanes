# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour worker.
Désormais hébergé dans app.infra.worker.
"""

from __future__ import annotations

import sys
from app.infra import worker as _mod

sys.modules[__name__] = _mod
