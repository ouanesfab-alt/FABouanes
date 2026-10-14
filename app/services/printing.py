# Backward compatibility shim — all functionality moved to app.infra.printing
import sys
from app.infra import printing as _printing
from app.infra.printing import *  # noqa: F401, F403
from app.infra.printing import (
    COMPANY_INFO,
    PRINT_LAYOUT,
    build_print_payload,
    generate_invoice_pdf,
)

__all__ = [
    "COMPANY_INFO",
    "PRINT_LAYOUT",
    "build_print_payload",
    "generate_invoice_pdf",
]

sys.modules["app.services.printing"] = _printing
