"""SQLAlchemy Core schema for Bookmarks Cerebro.

This module defines table metadata for the SQLite backend. It intentionally uses
SQLAlchemy Core (not ORM) to stay lightweight and dataclass-first.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa

logger = logging.getLogger("cerebro")

metadata = sa.MetaData()

bookmarks_table = sa.Table(
    "bookmarks",
    metadata,
    sa.Column("rowid", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("id", sa.String, unique=True, nullable=False),
    sa.Column("url", sa.String, nullable=False),
    sa.Column("title", sa.String, nullable=False),
    sa.Column("raw_folder_path", sa.String, nullable=True),
    sa.Column("add_date_epoch", sa.String, nullable=True),
    sa.Column("add_date_iso", sa.String, nullable=True),
    sa.Column("icon", sa.String, nullable=True),
    sa.Column("domain", sa.String, nullable=False, default=""),
    sa.Column("tld_plus_one", sa.String, nullable=False, default=""),
    sa.Column("category_breadcrumbs", sa.JSON, nullable=False, default=list),
    sa.Column("confidence_score", sa.Float, nullable=False, default=0.0),
    sa.Column("tags", sa.JSON, nullable=False, default=list),
    sa.Column("description", sa.Text, nullable=False, default=""),
    sa.Column("description_source", sa.String, nullable=False, default="synthetic"),
    sa.Column("inferred_metadata", sa.JSON, nullable=False, default=dict),
    sa.Column("fetched_metadata", sa.JSON, nullable=False, default=dict),
    sa.Column("duplicate_group_id", sa.String, nullable=True),
    sa.Column("duplicate_urls", sa.JSON, nullable=False, default=list),
    sa.Column("is_dead_link", sa.Boolean, nullable=False, default=False),
    sa.Column("http_status", sa.Integer, nullable=True),
    sa.Column("related_ids", sa.JSON, nullable=False, default=list),
    sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    sa.Index("ix_bookmarks_url", "url"),
    sa.Index("ix_bookmarks_domain", "domain"),
    sa.Index("ix_bookmarks_is_dead_link", "is_dead_link"),
)

tags_table = sa.Table(
    "tags",
    metadata,
    sa.Column(
        "bookmark_id",
        sa.String,
        sa.ForeignKey("bookmarks.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column("tag", sa.String, primary_key=True),
    sa.Index("ix_tags_tag", "tag"),
)

audit_log_table = sa.Table(
    "audit_log",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("action", sa.String, nullable=False),
    sa.Column("bookmark_id", sa.String, nullable=False),
    sa.Column("details", sa.JSON, nullable=False, default=dict),
    sa.Column("timestamp", sa.DateTime, server_default=sa.func.now()),
    sa.Index("ix_audit_log_bookmark_id", "bookmark_id"),
    sa.Index("ix_audit_log_timestamp", "timestamp"),
)


def create_tables(engine: sa.engine.Engine) -> None:
    """Create all schema objects on the supplied engine."""
    metadata.create_all(engine)
    _ensure_fts5(engine)


def drop_tables(engine: sa.engine.Engine) -> None:
    """Drop all schema objects on the supplied engine."""
    with engine.begin() as conn:
        conn.execute(sa.text("DROP TABLE IF EXISTS fts_bookmarks"))
    metadata.drop_all(engine)


def _ensure_fts5(engine: sa.engine.Engine) -> None:
    """Create the FTS5 virtual table and sync triggers if supported.

    SQLite must be compiled with FTS5. If not available, the error is logged
    and search falls back to ILIKE.
    """
    fts_columns = "title, description, tags"
    create_sql = f"""
    CREATE VIRTUAL TABLE IF NOT EXISTS fts_bookmarks USING fts5(
        {fts_columns},
        content='bookmarks',
        content_rowid='rowid',
        tokenize='porter unicode61'
    )
    """
    triggers = [
        """
        CREATE TRIGGER IF NOT EXISTS fts_bookmarks_insert
        AFTER INSERT ON bookmarks BEGIN
            INSERT INTO fts_bookmarks(rowid, title, description, tags)
            VALUES (new.rowid, new.title, new.description, new.tags);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS fts_bookmarks_delete
        AFTER DELETE ON bookmarks BEGIN
            INSERT INTO fts_bookmarks(fts_bookmarks, rowid, title, description, tags)
            VALUES ('delete', old.rowid, old.title, old.description, old.tags);
        END
        """,
        """
        CREATE TRIGGER IF NOT EXISTS fts_bookmarks_update
        AFTER UPDATE ON bookmarks BEGIN
            INSERT INTO fts_bookmarks(fts_bookmarks, rowid, title, description, tags)
            VALUES ('delete', old.rowid, old.title, old.description, old.tags);
            INSERT INTO fts_bookmarks(rowid, title, description, tags)
            VALUES (new.rowid, new.title, new.description, new.tags);
        END
        """,
    ]
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(create_sql))
            for trigger in triggers:
                conn.execute(sa.text(trigger))
    except sa.exc.OperationalError as exc:
        logger.warning(f"FTS5 not available ({exc}); search will fall back to ILIKE")
