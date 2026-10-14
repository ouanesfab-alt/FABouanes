# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour report_pages.
Désormais hébergé dans app.modules.reports.web.
"""

from __future__ import annotations

import sys
from app.modules.reports import web as _mod

sys.modules[__name__] = _mod
