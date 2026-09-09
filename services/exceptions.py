"""Custom exceptions and error response formatting.

All error responses follow a consistent envelope:

    {"detail": "Human-readable message", "error_code": "UNIQUE_IDENTIFIER"}
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


logger = logging.getLogger(__name__)


class AppException(HTTPException):
    """Base application exception with a machine-readable error code."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str,
    ) -> None:
        self.error_code = error_code
        super().__init__(status_code=status_code, detail=detail)


# ---------------------------------------------------------------------------
# Factory helpers for common error codes
# ---------------------------------------------------------------------------

ERROR_CODES = {
    "VALIDATION_ERROR": "VALIDATION_ERROR",
    "INVALID_CREDENTIALS": "INVALID_CREDENTIALS",
    "EMAIL_ALREADY_EXISTS": "EMAIL_ALREADY_EXISTS",
    "USER_NOT_FOUND": "USER_NOT_FOUND",
    "INVALID_USER_ID": "INVALID_USER_ID",
    "TOKEN_MISSING_SUB": "TOKEN_MISSING_SUB",
    "TOKEN_INVALID": "TOKEN_INVALID",
    "FORBIDDEN": "FORBIDDEN",
    "INTERNAL_ERROR": "INTERNAL_ERROR",
    "PASSWORD_TOO_LONG": "PASSWORD_TOO_LONG",
}


def validation_error(detail: str = "Validation error") -> AppException:
    return AppException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail, ERROR_CODES["VALIDATION_ERROR"])


def invalid_credentials() -> AppException:
    return AppException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password", ERROR_CODES["INVALID_CREDENTIALS"])


def email_already_exists() -> AppException:
    return AppException(status.HTTP_409_CONFLICT, "Email already registered", ERROR_CODES["EMAIL_ALREADY_EXISTS"])


def user_not_found() -> AppException:
    return AppException(status.HTTP_404_NOT_FOUND, "User not found", ERROR_CODES["USER_NOT_FOUND"])


def invalid_user_id() -> AppException:
    return AppException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid user ID", ERROR_CODES["INVALID_USER_ID"])


def token_missing_sub() -> AppException:
    return AppException(status.HTTP_401_UNAUTHORIZED, "Invalid token: missing subject", ERROR_CODES["TOKEN_MISSING_SUB"])


def token_invalid() -> AppException:
    return AppException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", ERROR_CODES["TOKEN_INVALID"])


def forbidden() -> AppException:
    return AppException(status.HTTP_403_FORBIDDEN, "You can only update your own profile", ERROR_CODES["FORBIDDEN"])


def internal_error() -> AppException:
    return AppException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error", ERROR_CODES["INTERNAL_ERROR"])


def password_too_long() -> AppException:
    return AppException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Password must be at most 128 characters", ERROR_CODES["PASSWORD_TOO_LONG"])


# ---------------------------------------------------------------------------
# Global exception handler for consistent error envelope
# ---------------------------------------------------------------------------


def app_exception_handler(request, exc: AppException) -> JSONResponse:
    """Convert AppException into the standard error envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code},
    )


def request_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a sanitized 422 response for request validation failures."""
    logger.warning(
        "Request validation failed: method=%s path=%s",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Invalid request data.",
            "error_code": ERROR_CODES["VALIDATION_ERROR"],
        },
    )


def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Convert any unhandled exception into a generic 500 response."""
    logger.error(
        "Unhandled exception during request: type=%s method=%s path=%s",
        type(exc).__name__,
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error", "error_code": ERROR_CODES["INTERNAL_ERROR"]},
    )