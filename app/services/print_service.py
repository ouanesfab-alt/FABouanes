# Backward compatibility — all functionality moved to app.services.printing
from app.services.printing import (  # noqa: F401
    COMPANY_INFO,
    PRINT_LAYOUT,
    build_print_payload,
    generate_invoice_pdf,
)
