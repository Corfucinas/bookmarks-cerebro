"""FastAPI + Jinja2 + htmx web dashboard for Bookmarks Cerebro.

This module is a backward-compatibility shim. App creation, middleware, and
the uvicorn launcher live in :mod:`cerebro.dashboard_app`; route handlers and
the ``get_db`` dependency live in :mod:`cerebro.dashboard_routes`.

Public symbols preserved for existing import sites:
    - ``app``            (used by tests/test_dashboard.py, tests/test_security.py)
    - ``run_dashboard``  (used by src/cerebro/cli.py)
    - ``get_db``         (used by tests/test_dashboard.py, tests/test_security.py)
"""

from __future__ import annotations

from src.cerebro.dashboard_app import app, run_dashboard
from src.cerebro.dashboard_routes import PER_PAGE, DBSession, get_db, templates

__all__ = ["DBSession", "PER_PAGE", "app", "get_db", "run_dashboard", "templates"]
