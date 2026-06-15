"""Tests for the extension ingestion server."""

import json
import sys
import threading
import time
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.db import create_tables, get_session
from cerebro.server import CerebroHandler


@pytest.fixture
def server_config(tmp_path: Path):
    """Provide a temp directory and DB URL for the test server."""
    db_path = tmp_path / "test.db"
    db_url = f"sqlite:///{db_path}"
    engine = __import__("sqlalchemy", fromlist=["create_engine"]).create_engine(db_url, future=True)
    create_tables(engine)
    engine.dispose()
    return {"db_url": db_url, "tmp_path": tmp_path}


@pytest.fixture
def running_server(server_config):
    """Start the threaded HTTPServer on an OS-assigned port."""
    from http.server import HTTPServer

    host = "127.0.0.1"
    port = 0  # OS-assigned

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


def test_api_ingest_persists_bookmark(running_server: str, server_config: dict):
    """POST /api/ingest creates a bookmark in SQLite."""
    payload = {
        "url": "https://example.com/test-server",
        "title": "Server Test Bookmark",
        "tags": ["server", "test"],
        "description": "Created by test_server.py",
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
        from cerebro.db import get_bookmark

        loaded = get_bookmark(session, data["id"])
        assert loaded is not None
        assert loaded.url == payload["url"]
        assert "server" in loaded.tags


def test_api_ingest_rejects_missing_url(running_server: str):
    """POST /api/ingest without url returns 400."""
    req = Request(
        f"{running_server}/api/ingest",
        data=json.dumps({"title": "no url"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    from urllib.error import HTTPError

    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 400
