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


def test_run_server_closes_socket(tmp_path: Path):
    """run_server must call server.server_close() on shutdown to avoid socket leaks."""
    from unittest.mock import MagicMock, patch

    db_path = tmp_path / "close.db"
    db_url = f"sqlite:///{db_path}"

    mock_server = MagicMock()
    started = threading.Event()
    shutdown_event = threading.Event()

    def serve_forever_side_effect():
        started.set()
        shutdown_event.wait(timeout=2)

    mock_server.serve_forever.side_effect = serve_forever_side_effect

    with patch("cerebro.server.HTTPServer", return_value=mock_server):
        from cerebro.server import run_server

        thread = threading.Thread(
            target=run_server,
            kwargs={"host": "127.0.0.1", "port": 0, "db_url": db_url},
            daemon=True,
        )
        thread.start()

        assert started.wait(timeout=2), "serve_forever did not start"

        def shutdown_side_effect():
            shutdown_event.set()

        mock_server.shutdown.side_effect = shutdown_side_effect
        mock_server.shutdown()
        thread.join(timeout=2)

    mock_server.server_close.assert_called()


def test_reexport_html_no_dummy_when_json_missing(tmp_path: Path):
    """_reexport_html must NOT write a garbage dummy bookmark when json_output is missing."""
    from cerebro.server import CerebroHandler

    html_output = tmp_path / "out.html"
    CerebroHandler.html_output = html_output
    CerebroHandler.json_output = None
    try:
        handler = CerebroHandler.__new__(CerebroHandler)
        handler._reexport_html()
        assert not html_output.exists(), "_reexport_html wrote garbage despite missing json_output"
    finally:
        CerebroHandler.html_output = None
        CerebroHandler.json_output = None


def test_api_ingest_rejects_empty_body(running_server: str):
    """POST /api/ingest with Content-Length: 0 returns 400 'Empty body'."""
    from urllib.error import HTTPError

    req = Request(
        f"{running_server}/api/ingest",
        data=b"",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 400


def test_api_ingest_rejects_invalid_json(running_server: str):
    """POST /api/ingest with malformed JSON returns 400."""
    from urllib.error import HTTPError

    req = Request(
        f"{running_server}/api/ingest",
        data=b"{not valid json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 400


def test_api_ingest_rejects_oversized_payload(running_server: str):
    """POST /api/ingest with Content-Length > MAX_CONTENT_LENGTH_BYTES returns 413."""
    from urllib.error import HTTPError

    from cerebro.security import MAX_CONTENT_LENGTH_BYTES

    huge = b"x" * (MAX_CONTENT_LENGTH_BYTES + 16)
    req = Request(
        f"{running_server}/api/ingest",
        data=huge,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 413


def test_api_ingest_rejects_invalid_content_length(running_server: str):
    """POST /api/ingest with non-integer Content-Length returns 400."""
    from http.client import HTTPConnection

    port = int(running_server.rsplit(":", 1)[1])
    conn = HTTPConnection("127.0.0.1", port=port)
    conn.putrequest("POST", "/api/ingest", skip_host=True)
    conn.putheader("Host", "127.0.0.1")
    conn.putheader("Content-Length", "not-a-number")
    conn.endheaders()
    resp = conn.getresponse()
    assert resp.status == 400
    body = json.loads(resp.read().decode())
    assert body["error"] == "Invalid Content-Length header"
    conn.close()


def test_do_options_returns_204_with_cors(running_server: str):
    """OPTIONS preflight returns 204 with CORS headers."""
    from http.client import HTTPConnection

    port = int(running_server.rsplit(":", 1)[1])
    conn = HTTPConnection("127.0.0.1", port=port)
    conn.request("OPTIONS", "/api/ingest")
    resp = conn.getresponse()
    assert resp.status == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"
    assert resp.headers.get("Access-Control-Allow-Methods") == "GET, POST, OPTIONS"
    conn.close()


def test_do_get_unknown_path_returns_404(running_server: str):
    """GET /unknown-path returns 404 JSON error."""
    from urllib.error import HTTPError

    with pytest.raises(HTTPError) as exc_info:
        urlopen(f"{running_server}/unknown-path")
    assert exc_info.value.code == 404


def test_api_ingest_with_json_output_appends(tmp_path: Path):
    """POST /api/ingest with json_output set appends to the JSON file."""
    import threading
    from http.client import HTTPConnection
    from http.server import HTTPServer

    from cerebro.db import create_tables
    from cerebro.server import CerebroHandler

    db_path = tmp_path / "append.db"
    db_url = f"sqlite:///{db_path}"
    engine = __import__("sqlalchemy", fromlist=["create_engine"]).create_engine(db_url, future=True)
    create_tables(engine)
    engine.dispose()

    json_output = tmp_path / "ingested.json"
    resolved_db_url = db_url
    resolved_json_output = json_output

    class BoundHandler(CerebroHandler):
        db_url = resolved_db_url
        json_output = resolved_json_output
        vault_dir = None
        html_output = None

    server = HTTPServer(("127.0.0.1", 0), BoundHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        payload = {
            "url": "https://example.com/append-test",
            "title": "Append Test",
            "tags": ["append"],
            "description": "",
        }
        conn = HTTPConnection("127.0.0.1", port=port)
        conn.request(
            "POST",
            "/api/ingest",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        assert resp.status == 200
        resp.read()
        conn.close()

        assert json_output.exists(), "json_output file should have been created"
        data = json.loads(json_output.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["url"] == payload["url"]
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=2)


def test_api_ingest_with_vault_dir_writes_obsidian(tmp_path: Path):
    """POST /api/ingest with vault_dir set writes an Obsidian markdown file."""
    import threading
    from http.client import HTTPConnection
    from http.server import HTTPServer

    from cerebro.db import create_tables
    from cerebro.server import CerebroHandler

    db_path = tmp_path / "vault.db"
    db_url = f"sqlite:///{db_path}"
    engine = __import__("sqlalchemy", fromlist=["create_engine"]).create_engine(db_url, future=True)
    create_tables(engine)
    engine.dispose()

    vault_dir = tmp_path / "vault"
    resolved_db_url = db_url
    resolved_vault_dir = vault_dir

    class BoundHandler(CerebroHandler):
        db_url = resolved_db_url
        json_output = None
        vault_dir = resolved_vault_dir
        html_output = None

    server = HTTPServer(("127.0.0.1", 0), BoundHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        payload = {
            "url": "https://example.com/vault-test",
            "title": "Vault Test",
            "tags": ["vault"],
            "description": "",
        }
        conn = HTTPConnection("127.0.0.1", port=port)
        conn.request(
            "POST",
            "/api/ingest",
            body=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        resp = conn.getresponse()
        assert resp.status == 200
        resp.read()
        conn.close()

        md_files = list(vault_dir.rglob("*.md"))
        assert len(md_files) == 1
        assert "https://example.com/vault-test" in md_files[0].read_text()
    finally:
        server.shutdown()
        server.server_close()
        t.join(timeout=2)


def test_reexport_html_writes_when_json_present(tmp_path: Path):
    """_reexport_html writes HTML when json_output exists with bookmarks."""
    from cerebro.exporter_json import export_json
    from cerebro.models import Bookmark
    from cerebro.server import CerebroHandler

    json_output = tmp_path / "out.json"
    html_output = tmp_path / "out.html"

    bm = Bookmark(id="reex-1", title="ReExport", url="https://example.com/reexport")
    export_json([bm], json_output)

    CerebroHandler.html_output = html_output
    CerebroHandler.json_output = json_output
    try:
        handler = CerebroHandler.__new__(CerebroHandler)
        handler._reexport_html()
        assert html_output.exists(), "HTML file should have been written"
        assert "https://example.com/reexport" in html_output.read_text()
    finally:
        CerebroHandler.html_output = None
        CerebroHandler.json_output = None


def test_append_to_json_creates_new_file(tmp_path: Path):
    """_append_to_json creates the JSON file when it does not yet exist."""
    from cerebro.models import Bookmark
    from cerebro.server import CerebroHandler

    json_output = tmp_path / "nested" / "new.json"

    bm = Bookmark(id="app-1", title="Append", url="https://example.com/append")

    CerebroHandler.json_output = json_output
    try:
        handler = CerebroHandler.__new__(CerebroHandler)
        handler._append_to_json(bm)
        assert json_output.exists(), "JSON file should have been created"
        data = json.loads(json_output.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["url"] == "https://example.com/append"
    finally:
        CerebroHandler.json_output = None


def test_do_post_unknown_path_returns_404(running_server: str):
    """POST to unknown path returns 404 JSON error."""
    from urllib.error import HTTPError

    req = Request(
        f"{running_server}/api/unknown",
        data=json.dumps({"x": 1}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(HTTPError) as exc_info:
        urlopen(req)
    assert exc_info.value.code == 404
