"""Session scope and database URL helpers for the SQLite backend.

Provides a context-managed SQLAlchemy session that auto-commits on success and
rolls back on error. Tables are created on-demand against the bound engine.
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from src.cerebro.db_schema import create_tables


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


__all__ = ["get_session", "_default_db_url"]
