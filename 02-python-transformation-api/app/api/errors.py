"""One error format for the Python service: RFC 9457 problem details (application/problem+json), ADR-011.

Three kinds of exception reach a client, and each gets a handler:
- HTTPException (Starlette's, which FastAPI's subclasses): 401 from the token check, 400 for a body that cannot be
  decoded (finding D30), 404 and 405 from routing. The status and the exception's own detail are kept; FastAPI's
  details here are fixed sentences, not user input.
- RequestValidationError: Pydantic found a broken rule (422 with an `errors` list in the gateway's field format), or
  the body is not well-formed JSON (422, no list: a JSON syntax error has a character position, not a field).
- StorageFailure: the database write failed. 500 with a fixed sentence and NOTHING from the exception (finding D6).
A last handler for Exception covers the unexpected.
"""

import logging
from collections.abc import Sequence
from http import HTTPStatus
from typing import Any, Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_JSON = "application/problem+json"
# The first element of a Pydantic location says where the value came from; it is not part of the field's name.
_SOURCES = {"body", "path", "query", "header", "cookie"}

logger = logging.getLogger(__name__)


class StorageFailure(Exception):
    """Raised by the transform route when the database write fails. Carries no message on purpose (finding D6)."""


def problem(
    request: Request,
    status_code: int,
    detail: str,
    errors: Optional[list[dict[str, str]]] = None,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": "about:blank",
        "title": HTTPStatus(status_code).phrase,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
    }
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(status_code=status_code, content=body, media_type=PROBLEM_JSON, headers=headers)


def field_path(location: Sequence[Any]) -> str:
    """('body', 'readings', 0, 'kwh_value') -> 'readings[0].kwh_value', the gateway's format (A4)."""
    parts = list(location[1:]) if location and location[0] in _SOURCES else list(location)
    path = ""
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        else:
            path += ("." if path else "") + str(part)
    return path


# Each handler takes `Exception` in its signature, which is what FastAPI's type for a handler requires, and checks the
# real type inside. (Annotating the narrower type works at run time but fails mypy's check of add_exception_handler.)

async def http_problem(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc
    detail = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    headers = dict(exc.headers) if exc.headers else None      # keeps e.g. the Allow header of a 405
    return problem(request, exc.status_code, detail, headers=headers)


async def validation_problem(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    details = exc.errors()
    # A JSON syntax error is reported by FastAPI as a validation error of type json_invalid, located at a character
    # position, not at a field. It gets the gateway's answer for the same case: a fixed detail and no errors list (P51).
    if any(error.get("type") == "json_invalid" for error in details):
        return problem(request, 422, "The request body is not well-formed JSON.")
    # `msg` only: Pydantic's `input` member carries the client's value, which is not echoed (A7).
    errors = [{"field": field_path(error["loc"]), "message": str(error["msg"])} for error in details]
    return problem(request, 422, "The request failed validation.", errors=errors)


async def storage_problem(request: Request, exc: Exception) -> JSONResponse:
    return problem(request, 500, "The readings could not be stored.")


async def unexpected_problem(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unexpected error (%s); answering 500", type(exc).__name__)
    return problem(request, 500, "An unexpected error occurred.")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_problem)
    app.add_exception_handler(RequestValidationError, validation_problem)
    app.add_exception_handler(StorageFailure, storage_problem)
    app.add_exception_handler(Exception, unexpected_problem)
