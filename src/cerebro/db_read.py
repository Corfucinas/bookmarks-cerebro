"""Read-only CRUD helpers for the SQLite backend.

All functions take an open :class:`sqlalchemy.orm.Session` and return
``Bookmark`` instances (or counts). None of them mutate the database.
"""

from __future__ import annotations

import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from src.cerebro.db_convert import _row_to_bookmark
from src.cerebro.db_schema import bookmarks_table
from src.cerebro.models import Bookmark

logger = logging.getLogger("cerebro")


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


def count_bookmarks(session: Session) -> int:
    """Return total number of bookmarks."""
    return int(
        session.execute(sa.select(sa.func.count()).select_from(bookmarks_table)).scalar_one()
    )


def count_dead_links(session: Session) -> int:
    """Return number of dead links."""
    stmt = sa.select(sa.func.count()).where(bookmarks_table.c.is_dead_link.is_(True))
    return int(session.execute(stmt.select_from(bookmarks_table)).scalar_one())


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


__all__ = [
    "get_bookmark",
    "get_bookmarks",
    "search_bookmarks",
    "search_bookmarks_fts",
    "count_bookmarks",
    "count_dead_links",
    "load_bookmarks",
    "get_dead_bookmarks",
]
