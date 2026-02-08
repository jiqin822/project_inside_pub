"""Domain error types."""
from typing import Optional


class DomainError(Exception):
    """Base domain error."""
    pass


class NotFoundError(DomainError):
    """Resource not found."""
    def __init__(self, resource: str, identifier: str):
        self.resource = resource
        self.identifier = identifier
        super().__init__(f"{resource} with id {identifier} not found")


class ValidationError(DomainError):
    """Validation error."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class AuthorizationError(DomainError):
    """Authorization error."""
    def __init__(self, message: str = "Not authorized"):
        self.message = message
        super().__init__(message)


class ConflictError(DomainError):
    """Resource conflict error."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)
