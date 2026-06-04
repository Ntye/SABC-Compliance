from __future__ import annotations


class DomainError(Exception):
    code: str = "DOMAIN_ERROR"

    def __init__(self, message: str = "") -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(DomainError):
    code = "NOT_FOUND"


class ConflictError(DomainError):
    code = "CONFLICT"


class ValidationError(DomainError):
    code = "VALIDATION"


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"


class ForbiddenError(DomainError):
    code = "FORBIDDEN"


class SSHConnectError(DomainError):
    code = "SSH_CONNECT"


class ExternalServiceError(DomainError):
    code = "EXTERNAL_SERVICE"
