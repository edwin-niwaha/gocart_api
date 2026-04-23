from __future__ import annotations

from rest_framework import status
from rest_framework.exceptions import ErrorDetail, ValidationError
from rest_framework.views import exception_handler


def _message_from_detail(value) -> str:
    if isinstance(value, list):
        return _message_from_detail(value[0]) if value else ""
    if isinstance(value, dict):
        if "detail" in value:
            return _message_from_detail(value["detail"])
        for item in value.values():
            message = _message_from_detail(item)
            if message:
                return message
        return ""
    return str(value)


def _code_from_detail(value, default: str) -> str:
    if isinstance(value, ErrorDetail):
        return value.code
    if isinstance(value, list):
        return _code_from_detail(value[0], default) if value else default
    if isinstance(value, dict):
        if "detail" in value:
            return _code_from_detail(value["detail"], default)
        for item in value.values():
            return _code_from_detail(item, default)
    return default


def _error_payload(*, detail, errors=None, code: str = "error") -> dict:
    return {
        "detail": str(detail),
        "errors": errors or {},
        "code": code,
    }


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    original_data = response.data

    if isinstance(exc, ValidationError):
        detail = _message_from_detail(original_data) or "Validation error."
        errors = original_data

        if isinstance(original_data, dict) and set(original_data.keys()) == {"detail"}:
            detail = _message_from_detail(original_data["detail"])
            errors = {}

        response.data = _error_payload(
            detail=detail,
            errors=errors,
            code="validation_error",
        )
        return response

    if isinstance(original_data, dict) and "detail" in original_data:
        response.data = _error_payload(
            detail=_message_from_detail(original_data["detail"]),
            code=_code_from_detail(
                original_data["detail"],
                getattr(exc, "default_code", "error"),
            ),
        )
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS and "wait" in original_data:
            response.data["wait"] = original_data["wait"]
        return response

    response.data = _error_payload(
        detail="Request failed.",
        errors=original_data,
        code=getattr(exc, "default_code", "error"),
    )
    return response
