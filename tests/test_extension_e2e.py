"""End-to-end tests for the browser-extension ingestion path.

These tests start the real Cerebro HTTP server on an ephemeral port, POST
bookmarks the same way the browser extension does, and verify that the data
lands in SQLite. This complements the JS unit tests in browser-extension/.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from http.server import HTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.db import create_tables, get_bookmark, get_session
from cerebro.server import CerebroHandler


@pytest.fixture
def server_config(tmp_path: Path):
    """Provide a temp directory and DB URL for the E2E server."""
    db_path = tmp_path / "extension-e2e.db"
    db_url = f"sqlite:///{db_path}"
    engine = __import__("sqlalchemy", fromlist=["create_engine"]).create_engine(db_url, future=True)
    create_tables(engine)
    engine.dispose()
    return {"db_url": db_url, "tmp_path": tmp_path}


@pytest.fixture
def running_server(server_config):
    """Start the threaded HTTPServer on an OS-assigned port."""
    host = "127.0.0.1"
    port = 0
    server = None

    def start():
        nonlocal server

        class BoundHandler(CerebroHandler):
            db_url = server_config["db_url"]
            json_output = None
            vault_dir = None
            html_output = None

        server = HTTPServer((host, port), BoundHandler)
        server.serve_forever()

    thread = threading.Thread(target=start, daemon=True)
    thread.start()
    for _ in range(50):
        if server is not None and server.server_address[1] != 0:
            break
        time.sleep(0.05)

    actual_port = server.server_address[1]
    base_url = f"http://{host}:{actual_port}"
    yield base_url
    server.shutdown()
    thread.join(timeout=2)


def test_api_health(running_server: str):
    """GET /api/health returns ok."""
    resp = urlopen(f"{running_server}/api/health")
    assert resp.status == 200
    data = json.loads(resp.read().decode())
    assert data["ok"] is True


def test_extension_ingest_persists_bookmark(running_server: str, server_config: dict):
    """POST /api/ingest from extension-style payload creates a bookmark in SQLite."""
    payload = {
        "url": "https://example.com/extension-e2e",
        "title": "Extension E2E Bookmark",
        "tags": ["extension", "e2e"],
        "description": "Sent by extension end-to-end test",
    }
    req = Request(
        f"{running_server}/api/ingest",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    resp = urlopen(req)
    assert resp.status == 200
    data = json.loads(resp.read().decode())
    assert data["id"]
    assert data["title"] == payload["title"]

    with get_session(server_config["db_url"]) as session:
        loaded = get_bookmark(session, data["id"])
        assert loaded is not None
        assert loaded.url == payload["url"]
        assert "extension" in loaded.tags
        assert loaded.description == payload["description"]


def test_extension_ingest_rejects_invalid_url(running_server: str):
    """POST /api/ingest with a non-http scheme returns 400."""
    req = Request(
        f"{running_server}/api/ingest",
        data=json.dumps({"url": "javascript://alert(1)", "title": "XSS"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 400


def test_extension_ingest_rejects_payload_too_large(running_server: str):
    """POST /api/ingest with a body over the size limit returns 413."""
    from cerebro.security import MAX_CONTENT_LENGTH_BYTES

    big_description = "x" * (MAX_CONTENT_LENGTH_BYTES + 1)
    req = Request(
        f"{running_server}/api/ingest",
        data=json.dumps(
            {"url": "https://example.com/big", "title": "Big", "description": big_description}
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 413


def test_extension_ingest_includes_security_headers(running_server: str):
    """Server responses include baseline security headers."""
    resp = urlopen(f"{running_server}/api/health")
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
