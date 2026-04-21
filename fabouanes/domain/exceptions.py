from __future__ import annotations


class FabouanesError(Exception):
    """Base class for explicit business/application errors."""


class ValidationError(FabouanesError):
    """Raised when an input payload is invalid."""


class NotFoundError(FabouanesError):
    """Raised when a requested business resource does not exist."""


class ConflictError(FabouanesError):
    """Raised when the current state prevents the requested action."""

