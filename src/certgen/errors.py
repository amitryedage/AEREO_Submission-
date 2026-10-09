"""Application error classes and uniform exception handlers."""

import logging
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("certgen.errors")


class AppError(Exception):
    """Base application exception returning structured error payload."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or []

    def to_dict(self) -> dict[str, Any]:
        """Format error body as standardized JSON structure."""
        data: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
        }
        if self.details:
            data["details"] = self.details
        return {"error": data}


class ValidationError(AppError):
    """Structural request validation error (HTTP 422)."""

    def __init__(
        self,
        message: str = "Request validation failed",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(
            code="VALIDATION_ERROR",
            message=message,
            status_code=422,
            details=details,
        )


class NotFoundError(AppError):
    """Resource not found error (HTTP 404)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=404)


class ConflictError(AppError):
    """Resource conflict or state not ready error (HTTP 409)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(code=code, message=message, status_code=409)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Handle custom AppError exceptions."""
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Transform FastAPI/Pydantic validation errors into standard format."""
    details: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = [str(x) for x in err.get("loc", []) if x != "body"]
        field = ".".join(loc) if loc else "body"
        msg = err.get("msg", "Invalid value")
        # Clean up Pydantic prefix if present
        if msg.startswith("Value error, "):
            msg = msg.removeprefix("Value error, ")
        details.append({"field": field, "message": msg})

    error = ValidationError(message="Request validation failed", details=details)
    return JSONResponse(status_code=error.status_code, content=error.to_dict())


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected server errors, ensuring internals are never leaked."""
    logger.exception("Unhandled server exception: %s", exc)
    error = AppError(
        code="INTERNAL_ERROR",
        message="An unexpected server error occurred",
        status_code=500,
    )
    return JSONResponse(status_code=500, content=error.to_dict())
