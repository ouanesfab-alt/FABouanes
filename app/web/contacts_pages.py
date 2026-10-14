# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour contacts_pages.
Désormais hébergé dans app.modules.clients.contacts_web.
"""

from __future__ import annotations

import sys
from app.modules.clients import contacts_web as _mod

sys.modules[__name__] = _mod
