"""Local HTTP server for browser-extension ingestion.

POST /api/ingest  → classify + enrich single bookmark, append to JSON, export to vault.
"""

from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

from src.cerebro.classifier import classify_bookmarks
from src.cerebro.enricher import enrich_bookmarks
from src.cerebro.exporter_html import export_html
from src.cerebro.exporter_obsidian import export_obsidian
from src.cerebro.fetcher import fetch_bookmarks
from src.cerebro.models import Bookmark
from src.cerebro.utils import compute_id, extract_domain, extract_tld_plus_one, load_json, save_json

logger = logging.getLogger("cerebro")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


class CerebroHandler(BaseHTTPRequestHandler):
    """Handle POST /api/ingest for single-bookmark pipeline."""

    def _json_response(self, status: int, data: dict[str, Any]) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self) -> None:
        if self.path != "/api/ingest":
            self._json_response(404, {"error": "Not found"})
            return

        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response(400, {"error": "Empty body"})
            return

        raw = self.rfile.read(content_length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            self._json_response(400, {"error": f"Invalid JSON: {e}"})
            return

        url = payload.get("url", "").strip()
        title = payload.get("title", "").strip() or url
        if not url:
            self._json_response(400, {"error": "Missing 'url'"})
            return

        # Run single-bookmark mini-pipeline
        bm = Bookmark(
            id=compute_id(url, title),
            url=url,
            title=title,
            domain=extract_domain(url),
            tld_plus_one=extract_tld_plus_one(url),
        )

        # Classify
        taxonomy_path = Path("taxonomy.yaml")
        bookmarks = classify_bookmarks([bm], taxonomy_path, train_ml=False)
        bm = bookmarks[0]

        # Fetch metadata (lightweight)
        bookmarks = fetch_bookmarks([bm], max_workers=1, timeout=10)
        bm = bookmarks[0]

        # Enrich
        bookmarks = enrich_bookmarks([bm])
        bm = bookmarks[0]

        # Append to existing enriched JSON if available
        enriched_json = Path("output/processed/enriched_bookmarks.json")
        if enriched_json.exists():
            data = load_json(enriched_json)
            if isinstance(data, list):
                data.append(bm.to_dict())
            else:
                data = [bm.to_dict()]
            save_json(enriched_json, data, pretty=True)
        else:
            save_json(enriched_json, [bm.to_dict()], pretty=True)

        # Export single-file to vault
        vault_dir = Path("output/vault")
        export_obsidian([bm], vault_dir)

        # Export HTML
        html_output = Path("output/processed/bookmarks_cerebro.html")
        if html_output.exists():
            # Re-export everything
            all_bookmarks = load_json(enriched_json)
            all_bms = [Bookmark.from_dict(d) for d in all_bookmarks]

            all_bms = [Bookmark.from_dict(d) for d in all_bookmarks]
            export_html(all_bms, html_output)
        else:
            export_html([bm], html_output)

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

    def log_message(self, format: str, *args: Any) -> None:
        logger.info(format % args)


def run_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Start blocking HTTP server."""
    server = HTTPServer((host, port), CerebroHandler)
    logger.info(f"Cerebro server running at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
        server.shutdown()
