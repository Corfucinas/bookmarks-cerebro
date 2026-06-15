"""SQLite persistence layer for Bookmarks Cerebro.

Uses SQLAlchemy Core with a synchronous SQLite engine. The public API is built
around a context-managed session and simple CRUD helpers that operate on the
`Bookmark` dataclass.
"""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session, sessionmaker

from src.cerebro.db_schema import audit_log_table, bookmarks_table, create_tables, tags_table
from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


@contextmanager
def get_session(db_url: str | None = None) -> Generator[Session, None, None]:
    """Yield a committed/rolled-back SQLAlchemy session scope.

    If ``db_url`` is not provided, ``data/cerebro.db`` relative to the current
    working directory is used.
    """
    url = db_url or _default_db_url()
    engine = sa.create_engine(url, future=True)
    create_tables(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
        engine.dispose()


def _default_db_url() -> str:
    return f"sqlite:///{Path('data/cerebro.db').resolve()}"


def _bookmark_to_row(bookmark: Bookmark) -> dict[str, Any]:
    """Flatten a Bookmark dataclass into a DB row dict.

    JSON columns accept Python lists/dicts directly when passed to SQLAlchemy.
    """
    return {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "raw_folder_path": bookmark.raw_folder_path,
        "add_date_epoch": bookmark.add_date_epoch,
        "add_date_iso": bookmark.add_date_iso,
        "icon": bookmark.icon,
        "domain": bookmark.domain,
        "tld_plus_one": bookmark.tld_plus_one,
        "category_breadcrumbs": bookmark.category_breadcrumbs,
        "confidence_score": bookmark.confidence_score,
        "tags": bookmark.tags,
        "description": bookmark.description,
        "description_source": bookmark.description_source,
        "inferred_metadata": bookmark.inferred_metadata,
        "fetched_metadata": bookmark.fetched_metadata,
        "duplicate_group_id": bookmark.duplicate_group_id,
        "duplicate_urls": bookmark.duplicate_urls,
        "is_dead_link": bookmark.is_dead_link,
        "http_status": bookmark.http_status,
        "related_ids": bookmark.related_ids,
    }


def _row_to_bookmark(row: sa.Row[Any]) -> Bookmark:
    """Hydrate a Bookmark from a bookmarks_table row."""
    return Bookmark(
        id=row.id,
        url=row.url,
        title=row.title,
        raw_folder_path=row.raw_folder_path,
        add_date_epoch=row.add_date_epoch,
        add_date_iso=row.add_date_iso,
        icon=row.icon,
        domain=row.domain or "",
        tld_plus_one=row.tld_plus_one or "",
        category_breadcrumbs=list(row.category_breadcrumbs or []),
        confidence_score=float(row.confidence_score or 0.0),
        tags=list(row.tags or []),
        description=row.description or "",
        description_source=row.description_source or "synthetic",
        inferred_metadata=dict(row.inferred_metadata or {}),
        fetched_metadata=dict(row.fetched_metadata or {}),
        duplicate_group_id=row.duplicate_group_id,
        duplicate_urls=list(row.duplicate_urls or []),
        is_dead_link=bool(row.is_dead_link),
        http_status=row.http_status,
        related_ids=list(row.related_ids or []),
    )


def upsert_bookmark(session: Session, bookmark: Bookmark) -> None:
    """Insert a bookmark or update it on ``id`` conflict."""
    row = _bookmark_to_row(bookmark)
    stmt = sqlite_insert(bookmarks_table).values(row)
    update_dict = {k: stmt.excluded[k] for k in row if k != "id"}
    session.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=update_dict))
    _sync_tags(session, bookmark)
    _log_action(session, bookmark.id, "upsert")


def _sync_tags(session: Session, bookmark: Bookmark) -> None:
    """Replace normalized tags for a bookmark."""
    session.execute(sa.delete(tags_table).where(tags_table.c.bookmark_id == bookmark.id))
    for tag in bookmark.tags:
        session.execute(
            sa.insert(tags_table).values(bookmark_id=bookmark.id, tag=tag),
        )


def _log_action(
    session: Session, bookmark_id: str, action: str, details: dict[str, Any] | None = None
) -> None:
    """Append an audit log entry."""
    session.execute(
        sa.insert(audit_log_table).values(
            action=action,
            bookmark_id=bookmark_id,
            details=details or {},
        ),
    )


def get_bookmark(session: Session, bookmark_id: str) -> Bookmark | None:
    """Fetch a single bookmark by ID."""
    row = session.execute(
        sa.select(bookmarks_table).where(bookmarks_table.c.id == bookmark_id),
    ).first()
    return _row_to_bookmark(row) if row else None


def get_bookmarks(
    session: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
    order_by: sa.Column[Any] | None = None,
) -> list[Bookmark]:
    """Fetch bookmarks ordered by ``updated_at`` descending by default."""
    sort_col = order_by if order_by is not None else bookmarks_table.c.updated_at.desc()
    stmt = sa.select(bookmarks_table).order_by(sort_col).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()
    return [_row_to_bookmark(row) for row in rows]


def search_bookmarks(session: Session, query: str, *, limit: int = 50) -> list[Bookmark]:
    """Basic substring search over title, url and description."""
    like = f"%{query}%"
    stmt = (
        sa.select(bookmarks_table)
        .where(
            sa.or_(
                bookmarks_table.c.title.ilike(like),
                bookmarks_table.c.url.ilike(like),
                bookmarks_table.c.description.ilike(like),
            ),
        )
        .order_by(bookmarks_table.c.updated_at.desc())
        .limit(limit)
    )
    rows = session.execute(stmt).all()
    return [_row_to_bookmark(row) for row in rows]


def search_bookmarks_fts(session: Session, query: str, *, limit: int = 50) -> list[Bookmark]:
    """Full-text search via SQLite FTS5, ranked by relevance.

    Falls back to ILIKE search if FTS5 is unavailable or the query is empty.
    """
    clean_query = query.strip()
    if not clean_query:
        return []
    try:
        # Build FTS5 table reference manually since it's a virtual table.
        fts = sa.Table(
            "fts_bookmarks",
            sa.MetaData(),
            sa.Column("rowid", sa.Integer),
            sa.Column("title", sa.String),
            sa.Column("description", sa.String),
            sa.Column("tags", sa.String),
        )
        match_clause = sa.text("fts_bookmarks MATCH :q").bindparams(q=clean_query)
        stmt = (
            sa.select(bookmarks_table)
            .join(fts, bookmarks_table.c.rowid == fts.c.rowid)
            .where(match_clause)
            .order_by(sa.text("rank"))
            .limit(limit)
        )
        rows = session.execute(stmt).all()
        return [_row_to_bookmark(row) for row in rows]
    except Exception as exc:
        logger.warning(f"FTS5 search failed ({exc}); falling back to ILIKE")
        return search_bookmarks(session, clean_query, limit=limit)


def update_bookmark_tags(session: Session, bookmark_id: str, tags: list[str]) -> bool:
    """Replace tags for a bookmark. Returns True if the bookmark exists."""
    existing = get_bookmark(session, bookmark_id)
    if existing is None:
        return False
    existing.tags = list(tags)
    upsert_bookmark(session, existing)
    return True


def delete_bookmark(session: Session, bookmark_id: str) -> bool:
    """Delete a bookmark by ID. Returns True if a row was removed."""
    result = session.execute(
        sa.delete(bookmarks_table).where(bookmarks_table.c.id == bookmark_id),
    )
    _log_action(session, bookmark_id, "delete")
    return bool(getattr(result, "rowcount", 0))


def count_bookmarks(session: Session) -> int:
    """Return total number of bookmarks."""
    return int(
        session.execute(sa.select(sa.func.count()).select_from(bookmarks_table)).scalar_one()
    )


def count_dead_links(session: Session) -> int:
    """Return number of dead links."""
    stmt = sa.select(sa.func.count()).where(bookmarks_table.c.is_dead_link.is_(True))
    return int(session.execute(stmt.select_from(bookmarks_table)).scalar_one())


def save_bookmarks(session: Session, bookmarks: list[Bookmark]) -> int:
    """Bulk upsert bookmarks and return the number written."""
    for bookmark in bookmarks:
        upsert_bookmark(session, bookmark)
    return len(bookmarks)


def load_bookmarks(session: Session, *, limit: int | None = None) -> list[Bookmark]:
    """Load all (or limited) bookmarks from the database."""
    return get_bookmarks(session, limit=limit)


def get_dead_bookmarks(
    session: Session,
    *,
    limit: int | None = None,
    offset: int = 0,
) -> list[Bookmark]:
    """Fetch bookmarks flagged as dead links."""
    stmt = (
        sa.select(bookmarks_table)
        .where(bookmarks_table.c.is_dead_link.is_(True))
        .order_by(bookmarks_table.c.updated_at.desc())
        .offset(offset)
    )
    if limit is not None:
        stmt = stmt.limit(limit)
    rows = session.execute(stmt).all()
    return [_row_to_bookmark(row) for row in rows]


def append_bookmark_tags(session: Session, bookmark_id: str, tags: list[str]) -> bool:
    """Append unique tags to a bookmark, preserving existing order."""
    existing = get_bookmark(session, bookmark_id)
    if existing is None:
        return False
    ordered = list(existing.tags)
    for tag in tags:
        if tag not in ordered:
            ordered.append(tag)
    existing.tags = ordered
    upsert_bookmark(session, existing)
    return True


__all__ = [
    "get_session",
    "upsert_bookmark",
    "get_bookmark",
    "get_bookmarks",
    "search_bookmarks",
    "search_bookmarks_fts",
    "update_bookmark_tags",
    "append_bookmark_tags",
    "delete_bookmark",
    "count_bookmarks",
    "count_dead_links",
    "get_dead_bookmarks",
    "save_bookmarks",
    "load_bookmarks",
]
