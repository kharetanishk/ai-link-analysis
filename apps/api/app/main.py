import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.errors import AppError, RateLimitedError, error_body, register_error_handlers
from app.schemas import ErrorResponse, LinkAnalysisRequest, LinkAnalysisResponse
from app.services.analysis_service import AnalysisService
from app.services.llm_service import LLMService
from app.services.website_extractor import WebsiteExtractor
from app.utils.cache import RateLimiter, TTLCache

DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")
ERROR_RESPONSES = {code: {"model": ErrorResponse} for code in (400, 415, 422, 429, 502, 503, 504)}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.fetch_timeout_seconds, connect=6.0),
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=10),
            follow_redirects=False,
        ) as client:
            llm = LLMService(settings)
            app.state.llm = llm
            app.state.analysis = AnalysisService(
                WebsiteExtractor(client, settings),
                llm,
                TTLCache(settings.cache_ttl_seconds, settings.cache_max_entries),
                settings,
            )
            app.state.tasks = set()
            app.state.limiter = RateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)
            if not llm.configured:
                logging.getLogger("app").warning("GEMINI_API_KEY is not set; /link-analysis will return 503")
            yield

    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Paste any business website URL and get AI-generated competitor, search query, SEO, "
            "services and target audience insights. Try **POST /link-analysis** below."
        ),
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.add_middleware(GZipMiddleware, minimum_size=1024)
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type"],
        )

    access_log = logging.getLogger("app.access")

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("x-request-id", "")[:64] or uuid.uuid4().hex[:16]
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        if not request.url.path.startswith(DOCS_PATHS):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
            )
        access_log.info(
            "%s %s %s %dms rid=%s",
            request.method,
            request.url.path,
            response.status_code,
            (time.perf_counter() - started) * 1000,
            request_id,
        )
        return response

    def rate_limit(request: Request) -> None:
        retry_after = request.app.state.limiter.check(request.client.host if request.client else "unknown")
        if retry_after:
            raise RateLimitedError(details={"retry_after": retry_after})

    @app.post(
        "/link-analysis",
        response_model=LinkAnalysisResponse,
        responses=ERROR_RESPONSES,
        tags=["Analysis"],
        summary="Analyze a website",
        dependencies=[Depends(rate_limit)],
    )
    async def link_analysis(body: LinkAnalysisRequest, request: Request) -> LinkAnalysisResponse:
        return await request.app.state.analysis.analyze(body.url)

    @app.post(
        "/link-analysis/stream",
        tags=["Analysis"],
        summary="Analyze a website with live progress (Server-Sent Events)",
        description=(
            "Same analysis as **POST /link-analysis**, streamed as `text/event-stream`. Emits `progress` events "
            "(`stage`, `percent`, `message`), then exactly one `result` event (the full report) or `error` event "
            "(the standard error envelope)."
        ),
        dependencies=[Depends(rate_limit)],
        response_class=StreamingResponse,
        responses={200: {"content": {"text/event-stream": {}}}},
    )
    async def link_analysis_stream(body: LinkAnalysisRequest, request: Request) -> StreamingResponse:
        queue: asyncio.Queue[tuple[str, dict]] = asyncio.Queue()

        def progress(stage: str, percent: int | None, message: str) -> None:
            queue.put_nowait(("progress", {"stage": stage, "percent": percent, "message": message}))

        async def run() -> None:
            try:
                result = await request.app.state.analysis.analyze(body.url, progress)
                queue.put_nowait(("result", result.model_dump(mode="json")))
            except AppError as exc:
                queue.put_nowait(("error", error_body(exc.code, exc.message, request, exc.details)))
            except Exception:
                logging.getLogger("app.errors").exception("unhandled error in stream")
                queue.put_nowait(("error", error_body(AppError.code, AppError.message, request)))

        # client chala bhi jaye to analysis poora ho ke cache me jaye; task ka reference rakhna zaroori hai
        task = asyncio.create_task(run())
        request.app.state.tasks.add(task)
        task.add_done_callback(request.app.state.tasks.discard)

        async def events():
            while True:
                try:
                    kind, data = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                yield f"event: {kind}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"
                if kind in ("result", "error"):
                    return

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
        )

    @app.get("/health", tags=["System"], summary="Service health")
    async def health(request: Request) -> dict:
        return {"status": "ok", "llm_configured": request.app.state.llm.configured, "model": settings.gemini_model}

    if (settings.static_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="web")
    else:

        @app.get("/", include_in_schema=False)
        async def root() -> dict:
            return {"name": settings.app_name, "docs": "/docs", "endpoint": "POST /link-analysis"}

    return app


app = create_app()
