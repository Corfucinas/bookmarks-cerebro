"""Administrative CLI commands for Bookmarks Cerebro.

Houses `config`, `migrate-db`, `db-status`, `serve`, `dashboard`, and `git-push`.
`serve` and `dashboard` resolve `run_server`/`run_dashboard` via a deferred
import from `src.cerebro.cli` so that `unittest.mock.patch("cerebro.cli.run_server")`
in tests keeps targeting the patched symbol.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from src.cerebro.db import count_bookmarks, count_dead_links, get_session


@click.command()
@click.pass_obj
def config(obj: dict[str, Any]) -> None:
    """Print the loaded configuration."""
    settings = obj["settings"]
    click.echo(f"database.path = {settings.database.path}")
    click.echo(f"database.migrations_path = {settings.database.migrations_path}")
    click.echo(f"server.host = {settings.server.host}")
    click.echo(f"server.port = {settings.server.port}")
    click.echo(f"dashboard.host = {settings.dashboard.host}")
    click.echo(f"dashboard.port = {settings.dashboard.port}")
    click.echo(f"fetcher.timeout = {settings.fetcher.timeout}")
    click.echo(f"fetcher.max_workers = {settings.fetcher.max_workers}")
    click.echo(f"ml.enable_classifier = {settings.ml.enable_classifier}")


@click.command()
@click.pass_obj
def migrate_db(obj: dict[str, Any]) -> None:
    """Create or upgrade the SQLite database schema."""
    settings = obj["settings"]
    with get_session(settings.db_url) as session:
        total = count_bookmarks(session)
    click.echo(f"✓ Database ready at {settings.database.path}")
    click.echo(f"  Existing bookmarks: {total}")


@click.command()
@click.pass_obj
def db_status(obj: dict[str, Any]) -> None:
    """Show database status and counts."""
    settings = obj["settings"]
    with get_session(settings.db_url) as session:
        total = count_bookmarks(session)
        dead = count_dead_links(session)
    click.echo(f"Database: {settings.database.path}")
    click.echo(f"  Total bookmarks: {total}")
    click.echo(f"  Dead links: {dead}")


@click.command()
@click.option("--host", type=str, default=None, help="Server host")
@click.option("--port", type=int, default=None, help="Server port")
@click.pass_obj
def serve(obj: dict[str, Any], host: str | None, port: int | None) -> None:
    """Start local HTTP server for browser-extension ingestion."""
    # Deferred import so tests can patch `cerebro.cli.run_server`.
    # `cerebro.cli` (not `src.cerebro.cli`) is used so the patched module object
    # matches the test patch target; `cerebro` is importable at runtime via
    # pyproject `where = ["src"]` and the test sys.path setup.
    from cerebro.cli import run_server

    settings = obj["settings"]
    run_server(
        host=host or settings.server.host,
        port=port or settings.server.port,
    )


@click.command()
@click.option("--host", type=str, default=None, help="Dashboard host")
@click.option("--port", type=int, default=None, help="Dashboard port")
@click.pass_obj
def dashboard(obj: dict[str, Any], host: str | None, port: int | None) -> None:
    """Start web dashboard for browsing bookmarks."""
    # Deferred import so tests can patch `cerebro.cli.run_dashboard`.
    from cerebro.cli import run_dashboard

    settings = obj["settings"]
    run_dashboard(
        host=host or settings.dashboard.host,
        port=port or settings.dashboard.port,
    )


@click.command()
@click.option(
    "--vault-dir",
    type=click.Path(path_type=Path),
    default="output/vault",
    help="Obsidian vault directory",
)
@click.option("--remote", type=str, default="origin", help="Git remote name")
@click.option("--branch", type=str, default="main", help="Git branch name")
def git_push(vault_dir: Path, remote: str, branch: str) -> None:
    """Auto-commit and push Obsidian vault to git."""
    import datetime
    import subprocess

    vault_dir = Path(vault_dir)
    if not (vault_dir / ".git").exists():
        click.echo(f"❌ {vault_dir} is not a git repository")
        return

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    msg = f"vault: auto-sync {ts}"

    try:
        subprocess.run(["git", "-C", str(vault_dir), "add", "."], check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", str(vault_dir), "commit", "-m", msg], check=True, capture_output=True
        )
        subprocess.run(
            ["git", "-C", str(vault_dir), "push", remote, branch], check=True, capture_output=True
        )
        click.echo(f"✓ Vault synced to {remote}/{branch} at {ts}")
    except subprocess.CalledProcessError as e:
        click.echo(f"⚠️ Git operation failed: {e}")
