# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour websockets.
Désormais hébergé dans app.infra.websockets.
"""

from __future__ import annotations

import sys
from app.infra import websockets as _mod

sys.modules[__name__] = _mod
