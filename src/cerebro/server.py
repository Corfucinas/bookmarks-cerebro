"""Local HTTP server for browser-extension ingestion.

POST /api/ingest  → persist bookmark to SQLite (and optionally JSON).
GET  /api/health  → server health check.
"""

from __future__ import annotations

import contextlib
import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from src.cerebro.config import load_settings
from src.cerebro.db import get_session, upsert_bookmark
from src.cerebro.exporter_html import export_html
from src.cerebro.exporter_json import export_json
from src.cerebro.exporter_obsidian import export_obsidian
from src.cerebro.models import Bookmark
from src.cerebro.security import MAX_CONTENT_LENGTH_BYTES, sanitize_ingest_payload
from src.cerebro.utils import compute_id, extract_domain, extract_tld_plus_one, load_json

logger = logging.getLogger("cerebro")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class CerebroHandler(BaseHTTPRequestHandler):
    """Handle extension-facing endpoints."""

    db_url: str = ""
    json_output: Path | None = None
    vault_dir: Path | None = None
    html_output: Path | None = None

    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    def _send_common_headers(self) -> None:
        for name, value in self.SECURITY_HEADERS.items():
            self.send_header(name, value)

    def _json_response(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self._send_common_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self._send_common_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/api/health":
            self._json_response(200, {"ok": True})
            return
        self._json_response(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/ingest":
            self._json_response(404, {"error": "Not found"})
            return

        content_length_header = self.headers.get("Content-Length", "0")
        try:
            content_length = int(content_length_header)
        except ValueError:
            self._json_response(400, {"error": "Invalid Content-Length header"})
            return
        if content_length == 0:
            self._json_response(400, {"error": "Empty body"})
            return
        if content_length > MAX_CONTENT_LENGTH_BYTES:
            # Discard the oversized body before responding so the client
            # receives a clean 413 instead of a broken-pipe error.
            with contextlib.suppress(ConnectionResetError, OSError):
                self.rfile.read(content_length)
            self._json_response(413, {"error": "Payload too large"})
            return

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._json_response(400, {"error": f"Invalid JSON: {e}"})
            return

        try:
            sanitized = sanitize_ingest_payload(payload)
        except HTTPException as exc:
            self._json_response(exc.status_code, {"error": exc.detail})
            return

        bm = Bookmark(
            id=compute_id(sanitized["url"], sanitized["title"]),
            url=sanitized["url"],
            title=sanitized["title"],
            domain=extract_domain(sanitized["url"]),
            tld_plus_one=extract_tld_plus_one(sanitized["url"]),
            tags=sanitized["tags"],
            description=sanitized["description"],
        )

        with get_session(self.db_url) as session:
            upsert_bookmark(session, bm)

        if self.json_output:
            self._append_to_json(bm)
        if self.vault_dir:
            export_obsidian([bm], self.vault_dir)
        if self.html_output:
            self._reexport_html()

        self._json_response(
            200,
            {
                "id": bm.id,
                "category": bm.category_path,
                "title": bm.title,
                "tags": bm.tags,
                "is_dead": bm.is_dead_link,
            },
        )

    def _append_to_json(self, bm: Bookmark) -> None:
        output = self.json_output
        assert output is not None
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.exists():
            data = load_json(output)
            if isinstance(data, list):
                data.append(bm.to_full_dict())
            else:
                data = [bm.to_full_dict()]
        else:
            data = [bm.to_full_dict()]
        export_json([Bookmark.from_dict(d) for d in data], output)

    def _reexport_html(self) -> None:
        output = self.html_output
        assert output is not None
        if not self.json_output or not self.json_output.exists():
            export_html([Bookmark(id="x", url="", title="")], output)
            return
        data = load_json(self.json_output)
        bookmarks = [Bookmark.from_dict(d) for d in data]
        export_html(bookmarks, output)

    def log_message(self, format: str, *args: Any) -> None:
        logger.info(format % args)


def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    db_url: str | None = None,
    json_output: Path | str | None = None,
    vault_dir: Path | str | None = None,
    html_output: Path | str | None = None,
) -> None:
    """Start blocking HTTP server with SQLite-backed ingestion."""
    settings = load_settings()
    resolved_db_url = db_url or settings.db_url

    class BoundHandler(CerebroHandler):
        db_url = resolved_db_url

    BoundHandler.json_output = Path(json_output) if json_output else None
    BoundHandler.vault_dir = Path(vault_dir) if vault_dir else None
    BoundHandler.html_output = Path(html_output) if html_output else None

    server = HTTPServer((host, port), BoundHandler)
    logger.info(f"Cerebro server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        server.shutdown()
