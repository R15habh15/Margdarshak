"""
middleware.py
Custom FastAPI middleware for the Margadarshak backend.

Provides:
  - Request/response logging with timing
  - Structured error handling and uniform error responses
  - Request ID injection for traceability
  - Basic rate limiting (in-memory, per IP)
"""

import time
import uuid
import logging
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------
# Request Logging Middleware
# ----------------------------------------------------------------

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Logs every incoming request with method, path, status code,
    and response time. Injects a unique X-Request-ID header.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())[:8]
        start_time = time.perf_counter()

        # Attach request ID to request state for downstream use
        request.state.request_id = request_id

        # Log incoming request
        logger.info(
            f"[{request_id}] --> {request.method} {request.url.path} "
            f"(client: {request.client.host if request.client else 'unknown'})"
        )

        try:
            response = await call_next(request)
        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"[{request_id}] !!! {request.method} {request.url.path} "
                f"UNHANDLED ERROR: {e} ({elapsed:.1f}ms)"
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error":      "Internal server error",
                    "request_id": request_id,
                    "detail":     str(e),
                },
            )

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"[{request_id}] <-- {request.method} {request.url.path} "
            f"STATUS={response.status_code} ({elapsed:.1f}ms)"
        )

        # Inject request ID into response headers
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{elapsed:.1f}ms"

        return response


# ----------------------------------------------------------------
# Rate Limiting Middleware
# ----------------------------------------------------------------

class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiter.

    Limits each IP to `max_requests` per `window_seconds`.
    WebSocket connections and static assets are excluded.

    Args:
        max_requests:    Max allowed requests per window
        window_seconds:  Time window in seconds
    """

    EXCLUDED_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}

    def __init__(self, app, max_requests: int = 120, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests    = max_requests
        self.window_seconds  = window_seconds
        self._request_log    = defaultdict(list)   # ip -> [timestamps]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths and WebSocket upgrades
        if (
            request.url.path in self.EXCLUDED_PATHS
            or request.headers.get("upgrade", "").lower() == "websocket"
        ):
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now       = time.time()
        window    = now - self.window_seconds

        # Remove timestamps outside the current window
        self._request_log[client_ip] = [
            t for t in self._request_log[client_ip] if t > window
        ]

        if len(self._request_log[client_ip]) >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            return JSONResponse(
                status_code=429,
                content={
                    "error":       "Too many requests",
                    "retry_after": self.window_seconds,
                },
                headers={"Retry-After": str(self.window_seconds)},
            )

        self._request_log[client_ip].append(now)
        return await call_next(request)


# ----------------------------------------------------------------
# Global Exception Handler (to register on FastAPI app)
# ----------------------------------------------------------------

async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all exception handler.
    Register with: app.add_exception_handler(Exception, global_exception_handler)
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unhandled exception [{request_id}]: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error":      "An unexpected error occurred",
            "request_id": request_id,
        },
    )
