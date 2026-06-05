from __future__ import annotations

import os
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


MAX_AUDIO_BYTES = 25 * 1024 * 1024
API_RATE_LIMIT = int(os.environ.get("API_RATE_LIMIT", "40"))
API_RATE_WINDOW_SECONDS = int(os.environ.get("API_RATE_WINDOW_SECONDS", "60"))
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN")

RequestHandler = Callable[[Request], Awaitable[Response]]


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestHandler) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; img-src 'self' data: blob:; "
            "connect-src 'self' https://*.modal.run https://*.tavus.io https://tavus.daily.co; "
            "frame-src https://*.daily.co https://tavus.daily.co https://*.tavus.io; "
            "media-src 'self' blob:; object-src 'none'; base-uri 'self'; form-action 'self'",
        )
        return response


class InMemoryRateLimiter:
    def __init__(self, limit: int = API_RATE_LIMIT, window_seconds: int = API_RATE_WINDOW_SECONDS) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = {}

    def check(self, request: Request) -> None:
        if not request.url.path.startswith("/api/"):
            return
        now = time.monotonic()
        client_host = request.client.host if request.client else "unknown"
        key = f"{client_host}:{request.url.path}"
        window_start = now - self.window_seconds
        existing = self._requests.get(key, deque())
        current = deque(timestamp for timestamp in existing if timestamp >= window_start)
        if len(current) >= self.limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
        current.append(now)
        self._requests = {**self._requests, key: current}


def require_admin_token(request: Request) -> None:
    if not ADMIN_TOKEN:
        raise HTTPException(status_code=404, detail="Not found")
    supplied = request.headers.get("X-Admin-Token")
    if supplied != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


def validate_upload_size(request: Request, actual_size: int) -> None:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared_size = int(content_length)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid Content-Length header.") from None
        if declared_size > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio upload is too large.")
    if actual_size > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio upload is too large.")
