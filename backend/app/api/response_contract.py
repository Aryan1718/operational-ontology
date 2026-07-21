"""Shared HTTP response envelope and request-context helpers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.schemas.common import ApiErrorDetail, ApiErrorResponse, ResponseMeta, SuccessResponse

REQUEST_ID_HEADER = "X-Request-Id"
_REQUEST_ID_STATE_KEY = "request_id"


def resolve_request_id(header_value: str | None) -> str:
    """Resolve a request identifier from the inbound header or generate one."""
    if header_value is not None:
        normalized = header_value.strip()
        if normalized:
            return normalized
    return f"req_{uuid4().hex}"


def store_request_id(request: Request, request_id: str) -> None:
    """Persist the resolved request identifier on the request state."""
    setattr(request.state, _REQUEST_ID_STATE_KEY, request_id)


def get_request_id(request: Request) -> str:
    """Return the shared request identifier for the current HTTP request."""
    request_id = getattr(request.state, _REQUEST_ID_STATE_KEY, None)
    if isinstance(request_id, str) and request_id.strip():
        return request_id

    resolved_request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))
    store_request_id(request, resolved_request_id)
    return resolved_request_id


def build_response_meta(request: Request) -> ResponseMeta:
    """Build shared success/error metadata for the current request."""
    return ResponseMeta(requestId=get_request_id(request))


def build_success_response(request: Request, data: Any) -> SuccessResponse[Any]:
    """Wrap a route payload in the shared success envelope."""
    return SuccessResponse[Any](data=data, meta=build_response_meta(request))


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build the shared structured error response and header."""
    request_id = get_request_id(request)
    payload = ApiErrorResponse(
        error=ApiErrorDetail(
            code=code,
            message=message,
            details=details or {},
        ),
        meta=ResponseMeta(requestId=request_id),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True),
        headers={REQUEST_ID_HEADER: request_id},
    )


def build_invalid_request_response(
    request: Request,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Return the standardized invalid-request envelope."""
    return build_error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="INVALID_REQUEST",
        message="The request is invalid.",
        details=details,
    )


def build_internal_error_response(request: Request) -> JSONResponse:
    """Return the standardized internal-error envelope."""
    return build_error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_ERROR",
        message="An unexpected error occurred.",
    )

