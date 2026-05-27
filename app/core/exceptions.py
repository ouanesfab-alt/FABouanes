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


def get_friendly_error_message(exc: Exception) -> str:
    from pydantic import ValidationError as PydanticValidationError
    if isinstance(exc, PydanticValidationError):
        return ", ".join([err["msg"] for err in exc.errors()])
    if isinstance(exc, BusinessError):
        return exc.message
    if isinstance(exc, (ValueError, AssertionError)):
        return str(exc)
    
    err_msg = str(exc).lower()
    if "foreign key" in err_msg or "violates foreign key constraint" in err_msg or "clé étrangère" in err_msg or "foreignkey" in err_msg:
        return "Action impossible : cet élément est lié à d'autres opérations enregistrées dans le système et ne peut pas être modifié ou supprimé."
    if "unique constraint" in err_msg or "duplicate key" in err_msg or "clé dupliquée" in err_msg or "contrainte unique" in err_msg or "uniqueviolation" in err_msg:
        return "Action impossible : cette valeur existe déjà. Veuillez utiliser un nom ou un identifiant unique."
    if "numeric value out of range" in err_msg or "valeur numérique en dehors des limites" in err_msg or "out of range" in err_msg or "numeric_value_out_of_range" in err_msg:
        return "Action impossible : un des montants ou quantités saisis dépasse les limites numériques autorisées."
    
    return f"Une erreur s'est produite : {type(exc).__name__}"
