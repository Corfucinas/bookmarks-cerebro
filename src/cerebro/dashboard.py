"""FastAPI + Jinja2 + htmx web dashboard for Bookmarks Cerebro."""

from __future__ import annotations

from collections import Counter
from collections.abc import Generator
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from src.cerebro.config import load_settings
from src.cerebro.db import (
    count_bookmarks,
    count_dead_links,
    get_bookmark,
    get_bookmarks,
    get_session,
    search_bookmarks,
    upsert_bookmark,
)
from src.cerebro.models import Bookmark
from src.cerebro.utils import compute_id

# Template directory relative to this file
TEMPLATES_DIR = Path(__file__).resolve().parent / "dashboard_templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

app = FastAPI(title="Bookmarks Cerebro Dashboard", version="1.0.0")

# Constants
PER_PAGE = 50


def get_db() -> Generator[Session, None, None]:
    """Dependency that yields a database session."""
    settings = load_settings()
    with get_session(settings.db_url) as session:
        yield session


DBSession = Annotated[Session, Depends(get_db)]


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
) -> HTMLResponse:
    """Render the bookmarks list page with pagination."""
    offset = (page - 1) * PER_PAGE
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
        },
    )


@app.get("/search", response_class=HTMLResponse)
async def search(
    request: Request,
    db: DBSession,
    q: str = "",
) -> HTMLResponse:
    """HTMX search endpoint returning bookmark rows fragment."""
    bookmarks = [] if not q else search_bookmarks(db, q, limit=50)

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


@app.get("/stats", response_class=HTMLResponse)
async def stats(request: Request, db: DBSession) -> HTMLResponse:
    """Render statistics page with bookmark counts and top categories."""
    total = count_bookmarks(db)
    dead_links = count_dead_links(db)

    # Get all bookmarks to compute top categories
    bookmarks = get_bookmarks(db, limit=10000)  # Reasonable limit for stats
    category_counts: Counter[str] = Counter()
    for bm in bookmarks:
        if bm.category_breadcrumbs:
            # Use the last breadcrumb as the primary category
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


@app.post("/api/ingest", response_class=JSONResponse)
async def ingest_bookmark(
    db: DBSession,
    url: str,
    title: str,
    tags: list[str] | None = None,
    description: str | None = None,
) -> JSONResponse:
    """Create or update a bookmark from browser extension or API.

    Returns the bookmark ID and creation status.
    """
    bookmark_id = compute_id(url, title)

    bookmark = Bookmark(
        id=bookmark_id,
        url=url,
        title=title,
        tags=tags or [],
        description=description or "",
        domain="",
        tld_plus_one="",
        category_breadcrumbs=[],
        confidence_score=0.0,
    )

    upsert_bookmark(db, bookmark)

    return JSONResponse(
        content={"id": bookmark_id, "status": "created"},
        status_code=201,
    )


def run_dashboard(host: str = "127.0.0.1", port: int = 8080) -> None:
    """Run the FastAPI dashboard server using uvicorn."""
    import uvicorn

    uvicorn.run(app, host=host, port=port)
