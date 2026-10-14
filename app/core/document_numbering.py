# -*- coding: utf-8 -*-
"""
Shim de compatibilité pour document_numbering.
Désormais hébergé dans app.infra.document_numbering.
"""

from __future__ import annotations

import sys
from app.infra import document_numbering as _mod

sys.modules[__name__] = _mod
