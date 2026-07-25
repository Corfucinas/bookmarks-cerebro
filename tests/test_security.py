"""Tests for shared security middleware and input validation."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.dashboard import app as dashboard_app
from cerebro.dashboard import get_db
from cerebro.db import create_tables
from cerebro.security import (
    MAX_CONTENT_LENGTH_BYTES,
    RateLimiter,
    _RequestSizeMiddleware,
    _SecurityHeadersMiddleware,
    add_security_middleware,
    sanitize_ingest_payload,
    validate_url,
)


@pytest.fixture
def db_session():
    """Provide a fresh file-based database session for security tests."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    db_url = f"sqlite:///{db_path}"
    engine = sa.create_engine(db_url, future=True)
    create_tables(engine)

    from sqlalchemy.orm import sessionmaker

    factory = sessionmaker(bind=engine)
    session = factory()

    yield session

    session.close()
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def dashboard_client(db_session):
    """Provide a TestClient with the security middleware active."""

    def override_get_db():
        yield db_session

    dashboard_app.dependency_overrides[get_db] = override_get_db
    with TestClient(dashboard_app) as client:
        yield client
    dashboard_app.dependency_overrides.clear()


def test_security_headers_present(dashboard_client):
    """Dashboard responses include baseline security headers."""
    response = dashboard_client.get("/bookmarks")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_request_size_limit_rejects_large_payloads():
    """Middleware returns 413 when Content-Length exceeds the maximum."""
    app = FastAPI()
    add_security_middleware(app)

    @app.post("/echo")
    async def echo():
        return {"ok": True}

    body = b"x" * (MAX_CONTENT_LENGTH_BYTES + 1)
    with TestClient(app) as client:
        response = client.post("/echo", content=body)
    assert response.status_code == 413
    assert "Payload too large" in response.text


def test_request_size_limit_allows_small_payloads():
    """Middleware allows requests under the size limit."""
    app = FastAPI()
    add_security_middleware(app)

    @app.post("/echo")
    async def echo():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post("/echo", content=b"hello")
    assert response.status_code == 200


def test_rate_limiter_allows_under_threshold():
    """RateLimiter permits requests up to the configured threshold."""
    limiter = RateLimiter(max_requests=3, window_seconds=60)
    assert limiter.is_allowed("client-a")
    assert limiter.is_allowed("client-a")
    assert limiter.is_allowed("client-a")
    assert not limiter.is_allowed("client-a")


def test_rate_limiter_tracks_clients_independently():
    """RateLimiter buckets are keyed by client IP."""
    limiter = RateLimiter(max_requests=2, window_seconds=60)
    assert limiter.is_allowed("client-a")
    assert limiter.is_allowed("client-b")
    assert limiter.is_allowed("client-b")
    assert not limiter.is_allowed("client-b")
    assert limiter.is_allowed("client-a")


def test_ingest_rejects_missing_url(dashboard_client):
    """POST /api/ingest without a URL returns 400."""
    response = dashboard_client.post("/api/ingest", json={"title": "no url"})
    assert response.status_code == 400
    assert "url" in response.json()["detail"].lower()


def test_ingest_rejects_bad_url_scheme(dashboard_client):
    """POST /api/ingest rejects non-http/https URLs."""
    response = dashboard_client.post(
        "/api/ingest", json={"url": "javascript://alert(1)", "title": "XSS"}
    )
    assert response.status_code == 400
    assert "http or https" in response.json()["detail"]


def test_ingest_rejects_too_long_url(dashboard_client):
    """POST /api/ingest rejects URLs exceeding the maximum length."""
    response = dashboard_client.post(
        "/api/ingest", json={"url": "https://example.com/" + "x" * 5000, "title": "Long"}
    )
    assert response.status_code == 400
    assert "URL exceeds" in response.json()["detail"]


def test_sanitize_ingest_payload_normalizes_data():
    """sanitize_ingest_payload cleans and validates a valid payload."""
    payload = {
        "url": "  https://example.com/path  ",
        "title": "  Title Here  ",
        "tags": ["  a  ", "b", "", "c" * 50],
        "description": "  A description  ",
    }
    sanitized = sanitize_ingest_payload(payload)
    assert sanitized["url"] == "https://example.com/path"
    assert sanitized["title"] == "Title Here"
    assert sanitized["tags"] == ["a", "b", "c" * 50]
    assert sanitized["description"] == "A description"


def test_validate_url_rejects_unsupported_schemes():
    """validate_url raises for file:// and javascript:// schemes."""
    with pytest.raises(Exception) as exc_info:
        validate_url("file:///etc/passwd")
    assert "http or https" in str(exc_info.value)


def test_security_headers_middleware_adds_headers():
    """_SecurityHeadersMiddleware appends security headers to responses."""
    app = FastAPI()
    app.add_middleware(_SecurityHeadersMiddleware)

    @app.get("/")
    async def root():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    assert response.headers["X-Frame-Options"] == "DENY"


def test_request_size_middleware_unit():
    """_RequestSizeMiddleware blocks oversized requests by Content-Length."""
    app = FastAPI()
    app.add_middleware(_RequestSizeMiddleware, max_bytes=100)

    @app.post("/")
    async def root():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.post("/", headers={"Content-Length": "200"})
    assert response.status_code == 413


def test_cors_allows_chrome_extension_origin():
    """CORS permits chrome-extension:// origins (used by the browser extension).

    Starlette's CORSMiddleware does not support `chrome-extension://*` as a
    wildcard pattern, so the default origins must fall back to `['*']` or
    otherwise permit extension origins.
    """
    app = FastAPI()
    add_security_middleware(app)

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    with TestClient(app) as client:
        response = client.get("/ping", headers={"Origin": "chrome-extension://abc123"})
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") is not None


def test_rate_limiter_cleans_empty_buckets():
    """RateLimiter removes buckets for clients whose entries have expired."""
    limiter = RateLimiter(max_requests=5, window_seconds=1)
    assert limiter.is_allowed("X")
    assert "X" in limiter._buckets

    # Wait past the window so X's entry is stale.
    import time as _time

    _time.sleep(1.1)

    # A different client triggers cleanup; X's stale bucket should be reclaimed.
    assert limiter.is_allowed("Y")
    assert "X" not in limiter._buckets


def test_request_size_rejects_chunked_encoding():
    """_RequestSizeMiddleware rejects state-changing requests with no Content-Length.

    Chunked transfer encoding omits Content-Length, which would otherwise bypass
    the size limit. The middleware must refuse such requests with 413.
    """
    from starlette.requests import Request as StarletteRequest

    app = FastAPI()
    app.add_middleware(_RequestSizeMiddleware, max_bytes=100)

    @app.post("/upload")
    async def upload():
        return {"ok": True}

    # Build a mock ASGI request with no Content-Length header (chunked encoding).
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [],  # no content-length
        "query_string": b"",
        "client": ("127.0.0.1", 1234),
        "server": ("testserver", 80),
        "scheme": "http",
    }

    async def receive():
        return {"type": "http.request", "body": b"x" * 1000, "more_body": False}

    request = StarletteRequest(scope, receive)
    middleware = _RequestSizeMiddleware(app, max_bytes=100)

    async def call_next(req):
        return Response(content=b"ok")

    import asyncio

    response = asyncio.run(middleware.dispatch(request, call_next))
    assert response.status_code == 413
    assert b"Payload too large" in response.body
