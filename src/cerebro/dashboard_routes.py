"""Dashboard route handlers for Bookmarks Cerebro.

All FastAPI routes (list, search, detail, edit, remove, bulk-tags, stats,
metrics, health, ingest) live here. They register onto the ``app`` instance
created in :mod:`cerebro.dashboard_app`.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

import sqlalchemy.exc
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.templating import Jinja2Templates
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy.orm import Session

from src.cerebro.config import Settings, load_settings
from src.cerebro.db import (
    append_bookmark_tags,
    count_bookmarks,
    count_dead_links,
    delete_bookmark,
    get_bookmark,
    get_bookmarks,
    get_dead_bookmarks,
    get_session,
    search_bookmarks_fts,
    upsert_bookmark,
)
from src.cerebro.models import Bookmark
from src.cerebro.security import sanitize_ingest_payload
from src.cerebro.utils import compute_id, extract_domain, extract_tld_plus_one

TEMPLATES_DIR = Path(__file__).resolve().parent / "dashboard_templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

PER_PAGE = 50

_settings_cache: Settings | None = None


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session."""
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_settings()
    with get_session(_settings_cache.db_url) as session:
        yield session


DBSession = Annotated[Session, Depends(get_db)]


def register_routes(app: FastAPI) -> None:
    """Register all dashboard routes onto the given FastAPI app instance."""
    _register(app)


def _register(app: FastAPI) -> None:  # noqa: C901 - route registration is inherently long
    """Attach every route handler to ``app``."""

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        """Redirect root to bookmarks list."""
        return templates.TemplateResponse(
            request=request,
            name="base.html",
            context={"redirect": "/bookmarks"},
            status_code=302,
            headers={"Location": "/bookmarks"},
        )

    @app.get("/bookmarks", response_class=HTMLResponse)
    async def list_bookmarks(
        request: Request,
        db: DBSession,
        page: int = 1,
        dead_only: bool = False,
    ) -> HTMLResponse:
        """Render the bookmarks list page with pagination and optional dead-link filter."""
        offset = (page - 1) * PER_PAGE
        if dead_only:
            bookmarks = get_dead_bookmarks(db, limit=PER_PAGE, offset=offset)
            total = count_dead_links(db)
        else:
            bookmarks = get_bookmarks(db, limit=PER_PAGE, offset=offset)
            total = count_bookmarks(db)

        total_pages = (total + PER_PAGE - 1) // PER_PAGE

        return templates.TemplateResponse(
            request=request,
            name="bookmarks/list.html",
            context={
                "bookmarks": bookmarks,
                "page": page,
                "total_pages": total_pages,
                "total": total,
                "dead_only": dead_only,
            },
        )

    @app.get("/search", response_class=HTMLResponse)
    async def search(
        request: Request,
        db: DBSession,
        q: str = "",
    ) -> HTMLResponse:
        """HTMX search endpoint returning bookmark rows fragment."""
        bookmarks = [] if not q else search_bookmarks_fts(db, q, limit=50)

        return templates.TemplateResponse(
            request=request,
            name="partials/bookmark_rows.html",
            context={"bookmarks": bookmarks},
        )

    @app.get("/bookmark/{bookmark_id}", response_class=HTMLResponse)
    async def bookmark_detail(
        request: Request,
        db: DBSession,
        bookmark_id: str,
    ) -> HTMLResponse:
        """Render the bookmark detail page."""
        bookmark = get_bookmark(db, bookmark_id)
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        return templates.TemplateResponse(
            request=request,
            name="bookmarks/detail.html",
            context={"bookmark": bookmark},
        )

    @app.get("/bookmark/{bookmark_id}/edit", response_class=HTMLResponse)
    async def edit_bookmark_form(
        request: Request,
        db: DBSession,
        bookmark_id: str,
    ) -> HTMLResponse:
        """Render the bookmark edit form."""
        bookmark = get_bookmark(db, bookmark_id)
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        return templates.TemplateResponse(
            request=request,
            name="bookmarks/edit.html",
            context={"bookmark": bookmark},
        )

    @app.post("/bookmark/{bookmark_id}/edit")
    async def edit_bookmark(
        db: DBSession,
        bookmark_id: str,
        title: str,
        tags: str,
        description: str = "",
    ) -> Response:
        """Update a bookmark's editable fields."""
        bookmark = get_bookmark(db, bookmark_id)
        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        bookmark.title = title
        bookmark.description = description
        bookmark.tags = [t.strip() for t in tags.split(",") if t.strip()]
        upsert_bookmark(db, bookmark)

        return Response(
            status_code=200,
            headers={"HX-Redirect": f"/bookmark/{bookmark_id}"},
        )

    @app.delete("/bookmark/{bookmark_id}")
    async def remove_bookmark(
        request: Request,
        db: DBSession,
        bookmark_id: str,
    ) -> Response:
        """Delete a bookmark."""
        removed = delete_bookmark(db, bookmark_id)
        if not removed:
            raise HTTPException(status_code=404, detail="Bookmark not found")

        if request.headers.get("HX-Request"):
            return Response(status_code=200, headers={"HX-Redirect": "/bookmarks"})
        return Response(status_code=302, headers={"Location": "/bookmarks"})

    @app.post("/bookmarks/bulk-tags")
    async def bulk_tags(
        request: Request,
        db: DBSession,
    ) -> Response:
        """Append tags to multiple bookmarks at once."""
        form = await request.form()
        ids = [str(value) for value in form.getlist("ids")]
        tags = str(form.get("tags", ""))
        new_tags = [t.strip() for t in tags.split(",") if t.strip()]
        for bookmark_id in ids:
            append_bookmark_tags(db, bookmark_id, new_tags)
        return Response(status_code=200)

    @app.get("/stats", response_class=HTMLResponse)
    async def stats(request: Request, db: DBSession) -> HTMLResponse:
        """Render statistics page with bookmark counts and top categories."""
        total = count_bookmarks(db)
        dead_links = count_dead_links(db)

        bookmarks = get_bookmarks(db, limit=10000)  # Reasonable limit for stats
        category_counts: Counter[str] = Counter()
        for bm in bookmarks:
            if bm.category_breadcrumbs:
                category_counts[bm.category_breadcrumbs[-1]] += 1

        top_categories = category_counts.most_common(10)

        return templates.TemplateResponse(
            request=request,
            name="bookmarks/stats.html",
            context={
                "total": total,
                "dead_links": dead_links,
                "top_categories": top_categories,
            },
        )

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics() -> PlainTextResponse:
        """Expose Prometheus metrics."""
        data = generate_latest()
        return PlainTextResponse(
            content=data.decode("utf-8"),
            media_type=CONTENT_TYPE_LATEST,
        )

    @app.get("/health", response_class=JSONResponse)
    async def health(db: DBSession) -> JSONResponse:
        try:
            total = count_bookmarks(db)
            return JSONResponse(
                content={"status": "ok", "bookmarks": total},
                status_code=200,
            )
        except (sqlalchemy.exc.SQLAlchemyError, OSError) as exc:
            return JSONResponse(
                content={"status": "error", "detail": str(exc)},
                status_code=503,
            )

    @app.post("/api/ingest", response_class=JSONResponse)
    async def ingest_bookmark(
        request: Request,
        db: DBSession,
    ) -> JSONResponse:
        """Create or update a bookmark from browser extension or API.

        Returns the bookmark ID and creation status.
        """
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

        sanitized = sanitize_ingest_payload(payload)
        bookmark_id = compute_id(sanitized["url"], sanitized["title"])

        bookmark = Bookmark(
            id=bookmark_id,
            url=sanitized["url"],
            title=sanitized["title"],
            tags=sanitized["tags"],
            description=sanitized["description"],
            domain=extract_domain(sanitized["url"]),
            tld_plus_one=extract_tld_plus_one(sanitized["url"]),
            category_breadcrumbs=[],
            confidence_score=0.0,
        )

        upsert_bookmark(db, bookmark)

        return JSONResponse(
            content={"id": bookmark_id, "status": "created"},
            status_code=201,
        )
