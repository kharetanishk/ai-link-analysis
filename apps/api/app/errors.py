import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app.errors")


class AppError(Exception):
    status_code = 500
    code = "internal_error"
    message = "Something went wrong on our side. Please try again."

    def __init__(self, message: str | None = None, *, details: dict | None = None):
        self.message = message or self.message
        self.details = details or {}
        super().__init__(self.message)


class InvalidURLError(AppError):
    status_code = 422
    code = "invalid_url"
    message = "Please enter a valid website address, for example https://example.com"


class BlockedURLError(AppError):
    status_code = 400
    code = "blocked_url"
    message = "This address points to a private or internal network and cannot be analyzed."


class SiteUnreachableError(AppError):
    status_code = 502
    code = "site_unreachable"
    message = "We could not reach this website. Check the address or try again later."


class SiteBlockedError(AppError):
    status_code = 502
    code = "site_access_denied"
    message = "This website refused automated access (bot protection or login wall)."


class SiteTimeoutError(AppError):
    status_code = 504
    code = "site_timeout"
    message = "The website took too long to respond."


class UnsupportedContentError(AppError):
    status_code = 415
    code = "unsupported_content"
    message = "This link does not point to a web page (HTML)."


class InsufficientContentError(AppError):
    status_code = 422
    code = "insufficient_content"
    message = "The page has too little readable text to analyze (it may need JavaScript to render)."


class LLMUnavailableError(AppError):
    status_code = 503
    code = "llm_unavailable"
    message = "The AI service is busy or unavailable right now. Please retry in a minute."


class LLMConfigError(AppError):
    status_code = 503
    code = "llm_not_configured"
    message = "The AI service is not configured on this server."


class LLMOutputError(AppError):
    status_code = 502
    code = "llm_invalid_output"
    message = "The AI returned an incomplete analysis. Please retry."


class RateLimitedError(AppError):
    status_code = 429
    code = "rate_limited"
    message = "Too many requests. Please wait a moment and try again."


def _body(code: str, message: str, request: Request, details: dict | None = None) -> dict:
    error = {"code": code, "message": message, "request_id": getattr(request.state, "request_id", None)}
    if details:
        error["details"] = details
    return {"success": False, "error": error}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        log.warning("%s: %s", exc.code, exc.message)
        headers = {"Retry-After": str(exc.details["retry_after"])} if "retry_after" in exc.details else None
        return JSONResponse(_body(exc.code, exc.message, request, exc.details), exc.status_code, headers=headers)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = [{"field": ".".join(str(p) for p in e["loc"][1:]), "issue": e["msg"]} for e in exc.errors()]
        return JSONResponse(
            _body(
                "invalid_request",
                'Request body must be JSON like {"url": "https://example.com"}.',
                request,
                {"fields": fields},
            ),
            422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(_body(f"http_{exc.status_code}", str(exc.detail), request), exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.exception("unhandled error")
        return JSONResponse(_body(AppError.code, AppError.message, request), 500)
