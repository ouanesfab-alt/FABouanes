# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour payment_service.
Désormais hébergé dans app.modules.payments.service.
"""

from __future__ import annotations

import sys
from app.modules.payments import service as _mod

sys.modules[__name__] = _mod
