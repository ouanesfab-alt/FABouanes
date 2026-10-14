# Backward compatibility — all functionality moved to app.infra.printing
from app.infra.printing import (  # noqa: F401
    COMPANY_INFO,
    PRINT_LAYOUT,
    build_print_payload,
    generate_invoice_pdf,
)
