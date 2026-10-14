# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour excel_import_service.
Désormais hébergé dans app.modules.admin.excel_import_service.
"""

from __future__ import annotations

import sys
from app.modules.admin import excel_import_service as _mod

sys.modules[__name__] = _mod
