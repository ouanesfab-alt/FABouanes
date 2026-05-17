from __future__ import annotations

class BusinessError(Exception):
    """Base exception for all business-related errors."""
    def __init__(self, message: str, code: str = "business_error", details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}

class NotFoundError(BusinessError):
    def __init__(self, resource: str, id: int | str):
        super().__init__(f"{resource} introuvable (ID: {id})", code="not_found")
        self.resource = resource
        self.id = id

class ValidationError(BusinessError):
    def __init__(self, message: str, field: str | None = None):
        super().__init__(message, code="validation_error")
        self.field = field
        if field:
            self.details = {"field": field}

class ConflictError(BusinessError):
    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message, code="conflict", details=details)

class PermissionDeniedError(BusinessError):
    def __init__(self, message: str = "Permission refusée"):
        super().__init__(message, code="permission_denied")

class AuthenticationRequiredError(BusinessError):
    def __init__(self, message: str = "Authentification requise"):
        super().__init__(message, code="authentication_required")
