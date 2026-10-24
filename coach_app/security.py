from __future__ import annotations

import hashlib
import hmac
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


# Hard cap per path for all visitors together. Protects the Tavus budget even if X-Forwarded-For is spoofed
# (direct calls to the modal.run URL). The web app runs in a single container (max_containers=1), so this is global.
GLOBAL_PATH_LIMITS = {
    "/api/session/create": int(os.environ.get("SESSION_CREATE_GLOBAL_LIMIT", "10")),
}
MAX_TRACKED_KEYS = 5000


class InMemoryRateLimiter:
    def __init__(
        self,
        limit: int = API_RATE_LIMIT,
        window_seconds: int = API_RATE_WINDOW_SECONDS,
        global_limits: dict[str, int] | None = None,
    ) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self.global_limits = GLOBAL_PATH_LIMITS if global_limits is None else global_limits
        self._requests: dict[str, deque[float]] = {}

    def check(self, request: Request) -> None:
        path = request.url.path
        if not path.startswith("/api/"):
            return
        now = time.monotonic()
        window_start = now - self.window_seconds
        if len(self._requests) > MAX_TRACKED_KEYS:
            self._evict(window_start)

        keys_and_limits = [(f"{client_ip(request)}:{path}", self.limit)]
        if path in self.global_limits:
            keys_and_limits.append((f"*:{path}", self.global_limits[path]))

        windows = {}
        for key, limit in keys_and_limits:
            current = deque(t for t in self._requests.get(key, deque()) if t >= window_start)
            if len(current) >= limit:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
            windows[key] = current
        for key, current in windows.items():
            current.append(now)
        self._requests = {**self._requests, **windows}

    def _evict(self, window_start: float) -> None:
        self._requests = {key: q for key, q in self._requests.items() if q and q[-1] >= window_start}


def client_ip(request: Request) -> str:
    # Behind the Vercel rewrite (coach.dreamtelligence.de) every request comes from Vercel; Vercel puts the
    # visitor IP first in X-Forwarded-For. Direct calls to the modal.run URL can spoof this header, so the
    # limiter stays best-effort there.
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first
    return request.client.host if request.client else "unknown"


def _session_secret() -> bytes:
    # Derived from the server-only Tavus key, so no extra secret has to be managed.
    base = os.environ.get("SESSION_SECRET") or os.environ.get("TAVUS_API_KEY") or os.environ.get("TAURUS_API_KEY") or ""
    if not base:
        raise HTTPException(status_code=503, detail="Session signing is not configured.")
    return hashlib.sha256(f"coachvoice-session:{base}".encode()).digest()


def issue_session_token(conversation_id: str) -> str:
    return hmac.new(_session_secret(), conversation_id.encode(), hashlib.sha256).hexdigest()


def require_session_token(request: Request, conversation_id: str) -> None:
    supplied = request.headers.get("X-Session-Token", "")
    if not supplied or not hmac.compare_digest(supplied, issue_session_token(conversation_id)):
        raise HTTPException(status_code=403, detail="Session nicht gefunden oder abgelaufen.")


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
