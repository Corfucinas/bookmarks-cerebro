"""Tests that CLI commands respect .cerebro.toml settings with CLI overrides."""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from click.testing import CliRunner

from cerebro.cli import cli


def test_serve_uses_config_host_port(tmp_path: Path):
    """cerebro serve reads host/port from config and CLI overrides win."""
    config = tmp_path / ".cerebro.toml"
    config.write_text("""
[server]
host = "0.0.0.0"
port = 9999
""")
    runner = CliRunner()

    with patch("cerebro.cli.run_server") as mock_run:
        result = runner.invoke(cli, ["--config", str(config), "serve"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs.get("host") == "0.0.0.0"
        assert kwargs.get("port") == 9999

    with patch("cerebro.cli.run_server") as mock_run:
        result = runner.invoke(
            cli,
            ["--config", str(config), "serve", "--host", "127.0.0.1", "--port", "8888"],
        )
        assert result.exit_code == 0, result.output
        args, kwargs = mock_run.call_args
        assert kwargs.get("host") == "127.0.0.1"
        assert kwargs.get("port") == 8888


def test_dashboard_uses_config_host_port(tmp_path: Path):
    """cerebro dashboard reads host/port from config and CLI overrides win."""
    config = tmp_path / ".cerebro.toml"
    config.write_text("""
[dashboard]
host = "0.0.0.0"
port = 7777
""")
    runner = CliRunner()

    with patch("cerebro.cli.run_dashboard") as mock_run:
        result = runner.invoke(cli, ["--config", str(config), "dashboard"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert kwargs.get("host") == "0.0.0.0"
        assert kwargs.get("port") == 7777

    with patch("cerebro.cli.run_dashboard") as mock_run:
        result = runner.invoke(
            cli,
            [
                "--config",
                str(config),
                "dashboard",
                "--host",
                "127.0.0.1",
                "--port",
                "6666",
            ],
        )
        assert result.exit_code == 0, result.output
        args, kwargs = mock_run.call_args
        assert kwargs.get("host") == "127.0.0.1"
        assert kwargs.get("port") == 6666


def test_pipeline_persists_to_db(tmp_path: Path):
    """cerebro pipeline --to-db persists enriched bookmarks to configured SQLite DB."""
    repo_root = Path(__file__).resolve().parents[1]
    sample_html = repo_root / ".github" / "testdata" / "sample.html"
    taxonomy = repo_root / "taxonomy.yaml"
    db_path = tmp_path / "cerebro.db"
    output_dir = tmp_path / "output"
    config = tmp_path / ".cerebro.toml"
    config.write_text(f"""
    [database]
    path = "{db_path}"
    """)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--config",
            str(config),
            "pipeline",
            str(sample_html),
            "--taxonomy",
            str(taxonomy),
            "--output-dir",
            str(output_dir),
            "--no-ml",
            "--to-db",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Saved" in result.output
    assert "bookmarks to database" in result.output

    from cerebro.config import load_settings
    from cerebro.db import count_bookmarks, get_session

    settings = load_settings(config)
    with get_session(settings.db_url) as session:
        assert count_bookmarks(session) > 0
