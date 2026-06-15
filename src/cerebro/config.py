"""Configuration loader for Bookmarks Cerebro.

Reads a ``.cerebro.toml`` file from the current working directory (or a path you
supply) and exposes a typed, immutable ``Settings`` object.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.cerebro.utils import ensure_dir

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True)
class DatabaseSettings:
    path: str = "data/cerebro.db"
    migrations_path: str = "src/cerebro/migrations"


@dataclass(frozen=True)
class ServerSettings:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(frozen=True)
class DashboardSettings:
    host: str = "127.0.0.1"
    port: int = 8080
    items_per_page: int = 50


@dataclass(frozen=True)
class FetcherSettings:
    timeout: int = 10
    max_workers: int = 10
    user_agent: str = "Bookmarks-Cerebro/1.0"


@dataclass(frozen=True)
class MLSettings:
    model_path: str = "data/model.joblib"
    enable_classifier: bool = True


@dataclass(frozen=True)
class Settings:
    database: DatabaseSettings = field(default_factory=DatabaseSettings)
    server: ServerSettings = field(default_factory=ServerSettings)
    dashboard: DashboardSettings = field(default_factory=DashboardSettings)
    fetcher: FetcherSettings = field(default_factory=FetcherSettings)
    ml: MLSettings = field(default_factory=MLSettings)

    @property
    def db_url(self) -> str:
        """Return SQLAlchemy-compatible SQLite URL for the configured database."""
        path = Path(self.database.path).resolve()
        ensure_dir(path.parent)
        return f"sqlite:///{path}"


def load_settings(path: Path | str | None = None) -> Settings:
    """Load ``.cerebro.toml`` from ``path`` or the current working directory.

    Missing files are handled gracefully by returning default settings.
    """
    path = Path.cwd() / ".cerebro.toml" if path is None else Path(path)

    if not path.exists():
        return Settings()

    raw = path.read_text(encoding="utf-8")
    data = tomllib.loads(raw)
    return _build_settings(data)


def _build_settings(data: dict[str, Any]) -> Settings:
    """Assemble a typed ``Settings`` object from a parsed TOML dict."""
    return Settings(
        database=_section(data, "database", DatabaseSettings),
        server=_section(data, "server", ServerSettings),
        dashboard=_section(data, "dashboard", DashboardSettings),
        fetcher=_section(data, "fetcher", FetcherSettings),
        ml=_section(data, "ml", MLSettings),
    )


def _section(data: dict[str, Any], key: str, klass: type[Any]) -> Any:
    """Instantiate a settings dataclass from a TOML section, using defaults for missing keys."""
    section_data = data.get(key, {})
    defaults = {
        f.name: f.default for f in dataclasses.fields(klass) if f.default is not dataclasses.MISSING
    }
    merged = {**defaults, **section_data}
    return klass(**{k: v for k, v in merged.items() if k in klass.__dataclass_fields__})
