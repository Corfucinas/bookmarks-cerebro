"""Smoke tests for configuration loader."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.config import load_settings


def test_default_settings():
    settings = load_settings("/nonexistent/path/.cerebro.toml")
    assert settings.database.path == "data/cerebro.db"
    assert settings.server.host == "127.0.0.1"
    assert settings.server.port == 8765
    assert settings.dashboard.items_per_page == 50


def test_load_from_toml(tmp_path):
    config_path = tmp_path / ".cerebro.toml"
    config_path.write_text(
        """
[database]
path = "custom.db"

[server]
host = "0.0.0.0"
port = 9999

[dashboard]
items_per_page = 100
""",
        encoding="utf-8",
    )
    settings = load_settings(config_path)
    assert settings.database.path == "custom.db"
    assert settings.server.host == "0.0.0.0"
    assert settings.server.port == 9999
    assert settings.dashboard.items_per_page == 100
    # Unchanged sections keep defaults
    assert settings.fetcher.timeout == 10


def test_db_url_uses_absolute_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / ".cerebro.toml"
    config_path.write_text('[database]\npath = "test.db"\n', encoding="utf-8")
    settings = load_settings(config_path)
    assert settings.db_url.startswith("sqlite:///")
    assert "test.db" in settings.db_url


def test_load_settings_malformed_toml(tmp_path):
    """Malformed TOML should raise a clear ValueError mentioning the file path."""
    import pytest

    config_path = tmp_path / ".cerebro.toml"
    config_path.write_text("key = ", encoding="utf-8")  # no value

    with pytest.raises(ValueError, match=str(config_path)):
        load_settings(config_path)
