# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour image_optimizer.
Désormais hébergé dans app.infra.image_optimizer.
"""

from __future__ import annotations

import sys
from app.infra import image_optimizer as _mod

sys.modules[__name__] = _mod
