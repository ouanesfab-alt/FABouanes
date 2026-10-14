# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour storage.
Désormais hébergé dans app.infra.storage.
"""

from __future__ import annotations

import sys
from app.infra import storage as _mod

sys.modules[__name__] = _mod
