"""Security utilities shared by dashboard and extension server.

Provides input validation, security headers, CORS rules, request-size limits,
and a small in-memory rate limiter so both HTTP frontends behave consistently.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# --- Validation constants ---
MAX_URL_LENGTH = 4096
MAX_TITLE_LENGTH = 500
MAX_DESCRIPTION_LENGTH = 4096
MAX_TAG_LENGTH = 100
MAX_TAGS = 50
MAX_CONTENT_LENGTH_BYTES = 1024 * 1024  # 1 MiB
ALLOWED_URL_SCHEMES = {"http", "https"}

# --- Security headers ---
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' unpkg.com; "
        "style-src 'self' 'unsafe-inline' cdn.jsdelivr.net unpkg.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    ),
}


class _SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value
        return response


class _RequestSizeMiddleware(BaseHTTPMiddleware):
    """Reject requests whose Content-Length exceeds the configured maximum."""

    def __init__(self, app: Any, max_bytes: int = MAX_CONTENT_LENGTH_BYTES) -> None:
        super().__init__(app)
        self.max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError as exc:
                return Response(
                    status_code=400,
                    content=f"Invalid Content-Length header: {exc}".encode(),
                )
            if size > self.max_bytes:
                return Response(status_code=413, content=b"Payload too large")
        return await call_next(request)


class RateLimiter:
    """Simple per-IP token-bucket-ish rate limiter.

    Tracks request timestamps in a deque and denies clients that exceed
    ``max_requests`` within ``window_seconds``. Not distributed: sufficient
    for a local single-process server.
    """

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.monotonic()
        window_start = now - self.window_seconds
        bucket = self._buckets.get(client_ip, deque())

        # Drop old entries outside the window
        while bucket and bucket[0] < window_start:
            bucket.popleft()

        allowed = len(bucket) < self.max_requests
        if allowed:
            bucket.append(now)

        if bucket:
            self._buckets[client_ip] = bucket
        elif client_ip in self._buckets:
            del self._buckets[client_ip]

        return allowed


class _RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply RateLimiter to state-changing routes."""

    def __init__(
        self,
        app: Any,
        max_requests: int = 60,
        window_seconds: int = 60,
        methods: set[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.limiter = RateLimiter(max_requests=max_requests, window_seconds=window_seconds)
        self.methods = methods or {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in self.methods:
            client_ip = _client_ip(request)
            if not self.limiter.is_allowed(client_ip):
                return Response(status_code=429, content=b"Rate limit exceeded")
        return await call_next(request)


def _client_ip(request: Request) -> str:
    """Best-effort client IP, preferring X-Forwarded-For last entry when present."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[-1].strip() or _request_host(request) or "unknown"
    return _request_host(request) or "unknown"


def _request_host(request: Request) -> str | None:
    """Return request client host if available."""
    return request.client.host if request.client else None


def add_security_middleware(app: FastAPI, cors_origins: list[str] | None = None) -> None:
    """Register security, size, CORS, and rate-limit middleware on a FastAPI app."""
    app.add_middleware(_SecurityHeadersMiddleware)
    app.add_middleware(_RequestSizeMiddleware, max_bytes=MAX_CONTENT_LENGTH_BYTES)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["http://localhost:8765", "chrome-extension://*"],
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-Requested-With"],
        allow_credentials=False,
        max_age=600,
    )
    app.add_middleware(_RateLimitMiddleware)


# --- Input validation ---


def validate_url(url: str | None) -> str:
    """Return a stripped URL or raise HTTPException 400 for invalid input."""
    if not url or not isinstance(url, str):
        raise HTTPException(status_code=400, detail="Missing or invalid 'url'")
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        raise HTTPException(status_code=400, detail="URL exceeds maximum length")
    parsed_scheme = url.split(":", 1)[0].lower() if ":" in url else ""
    if parsed_scheme not in ALLOWED_URL_SCHEMES:
        raise HTTPException(status_code=400, detail="URL must use http or https scheme")
    return url


def validate_title(title: str | None, url: str) -> str:
    """Return a stripped title, falling back to the URL if empty."""
    if not isinstance(title, str):
        title = ""
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        raise HTTPException(status_code=400, detail="Title exceeds maximum length")
    return title or url


def validate_tags(tags: Any) -> list[str]:
    """Return a sanitized list of tag strings."""
    if tags is None:
        return []
    if not isinstance(tags, list):
        raise HTTPException(status_code=400, detail="'tags' must be a list of strings")
    if len(tags) > MAX_TAGS:
        raise HTTPException(status_code=400, detail=f"Too many tags (max {MAX_TAGS})")
    result: list[str] = []
    for raw in tags:
        if not isinstance(raw, str):
            raise HTTPException(status_code=400, detail="Each tag must be a string")
        cleaned = raw.strip()
        if not cleaned:
            continue
        if len(cleaned) > MAX_TAG_LENGTH:
            raise HTTPException(status_code=400, detail="Tag exceeds maximum length")
        result.append(cleaned)
    return result


def validate_description(description: Any) -> str:
    """Return a stripped description string bounded by max length."""
    if description is None:
        return ""
    if not isinstance(description, str):
        raise HTTPException(status_code=400, detail="'description' must be a string")
    text: str = description.strip()
    if len(text) > MAX_DESCRIPTION_LENGTH:
        raise HTTPException(status_code=400, detail="Description exceeds maximum length")
    return text


def sanitize_ingest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and sanitize an extension/API ingestion payload."""
    url = validate_url(payload.get("url"))
    title = validate_title(payload.get("title"), url)
    tags = validate_tags(payload.get("tags"))
    description = validate_description(payload.get("description"))
    return {
        "url": url,
        "title": title,
        "tags": tags,
        "description": description,
    }
