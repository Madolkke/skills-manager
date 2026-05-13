class DomainError(Exception):
    """Base class for domain invariant failures."""


class NotFoundError(DomainError):
    """Raised when a referenced domain object does not exist."""


class InvariantError(DomainError):
    """Raised when a command would violate a domain rule."""


class PermissionDeniedError(DomainError):
    """Raised when an actor lacks permission for a protected action."""
