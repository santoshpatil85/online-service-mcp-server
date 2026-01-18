"""Error types for MCP Server."""
from typing import Any, Optional


class MCPError(Exception):
    """Base MCP error."""

    def __init__(
        self, message: str, error_code: str = "INTERNAL_ERROR", details: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Initialize MCPError.
        
        Args:
            message: Error message.
            error_code: Machine-readable error code.
            details: Additional error details.
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary."""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(MCPError):
    """Input validation error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, "VALIDATION_ERROR", details)


class ServiceError(MCPError):
    """Downstream service error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, "SERVICE_ERROR", details)


class AuthenticationError(MCPError):
    """Authentication/authorization error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class TimeoutError(MCPError):
    """Operation timeout error."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message, "TIMEOUT_ERROR", details)
