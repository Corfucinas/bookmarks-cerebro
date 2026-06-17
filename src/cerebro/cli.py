"""CLI entrypoint for Bookmarks Cerebro.

This module owns the top-level `cli` group and the core single-stage commands
(parse, classify, enrich, dedup, search). Subcommand groups and admin
commands live in dedicated modules and are registered here so that
`from src.cerebro.cli import cli` and the `cerebro` console script keep working.

`run_server` and `run_dashboard` are re-exported (not called here) so that
`unittest.mock.patch("cerebro.cli.run_server")` and `patch("cerebro.cli.run_dashboard")`
have a target attribute on this module — see tests/test_cli_config_overrides.py.
"""

from __future__ import annotations

import logging
from pathlib import Path

import click

from src.cerebro import __version__
from src.cerebro.classifier import classify_bookmarks

# Register subgroup + sibling commands. Imports are absolute per AGENTS.md.
from src.cerebro.cli_admin import (
    config as config_cmd,
)
from src.cerebro.cli_admin import (
    dashboard as dashboard_cmd,
)
from src.cerebro.cli_admin import (
    db_status,
    git_push,
    migrate_db,
)
from src.cerebro.cli_admin import (
    serve as serve_cmd,
)
from src.cerebro.cli_export_group import export
from src.cerebro.cli_graph import crosslinks, tag_graph
from src.cerebro.cli_pipeline import pipeline
from src.cerebro.config import load_settings
from src.cerebro.dashboard import run_dashboard
from src.cerebro.dedup import detect_duplicates
from src.cerebro.enricher import enrich_bookmarks
from src.cerebro.models import Bookmark
from src.cerebro.parser import parse_bookmarks
from src.cerebro.search import search_from_file
from src.cerebro.server import run_server
from src.cerebro.utils import load_json, save_json, setup_logging

# Re-exports kept as module attributes so test patches targeting
# `cerebro.cli.run_server` / `cerebro.cli.run_dashboard` resolve correctly.
__all__ = [
    "cli",
    "main",
    "run_server",
    "run_dashboard",
]

logger = logging.getLogger("cerebro")


@click.group()
@click.version_option(version=__version__, prog_name="cerebro")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--config", "-c", type=click.Path(path_type=Path), help="Path to .cerebro.toml")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, config: Path | None) -> None:
    """Bookmarks Cerebro — parse, categorize, enrich, and export bookmarks."""
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = load_settings(config)


@cli.command()
@click.argument("input_html", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default="data/processed/raw_bookmarks.json"
)
def parse(input_html: Path, output: Path) -> None:
    """Parse Netscape Bookmark HTML to raw JSON."""
    bookmarks = parse_bookmarks(input_html)

    save_json(output, [bm.to_dict() for bm in bookmarks])
    click.echo(f"✓ Parsed {len(bookmarks)} bookmarks → {output}")


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--taxonomy", "-t", type=click.Path(exists=True, path_type=Path), default="taxonomy.yaml"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/classified_bookmarks.json",
)
@click.option("--no-ml", is_flag=True, help="Skip ML fallback classification")
def classify(input_json: Path, taxonomy: Path, output: Path, no_ml: bool) -> None:
    """Classify bookmarks into taxonomy."""

    data = load_json(input_json)

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = classify_bookmarks(bookmarks, taxonomy, train_ml=not no_ml)

    save_json(output, [bm.to_dict() for bm in bookmarks])
    click.echo(f"✓ Classified {len(bookmarks)} bookmarks → {output}")


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/enriched_bookmarks.json",
)
def enrich(input_json: Path, output: Path) -> None:
    """Enrich bookmarks with tags and descriptions."""

    data = load_json(input_json)

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = enrich_bookmarks(bookmarks)

    save_json(output, [bm.to_dict() for bm in bookmarks])
    click.echo(f"✓ Enriched {len(bookmarks)} bookmarks → {output}")


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/deduped_bookmarks.json",
)
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["exact", "normalized", "hash", "fuzzy"], case_sensitive=False),
    default="exact",
    help="Dedup mode: exact|normalized|hash|fuzzy",
)
@click.option(
    "--threshold",
    "-t",
    type=float,
    default=0.85,
    help="Fuzzy similarity threshold (0.0-1.0)",
)
def dedup(input_json: Path, output: Path, mode: str, threshold: float) -> None:
    """Detect and mark duplicate bookmarks."""

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = detect_duplicates(bookmarks, mode=mode, similarity_threshold=threshold)

    save_json(output, [bm.to_dict() for bm in bookmarks])
    groups = {bm.duplicate_group_id for bm in bookmarks if bm.duplicate_group_id}
    click.echo(f"✓ Deduped ({mode}): {len(groups)} groups → {output}")


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.argument("query")
@click.option("--top-k", type=int, default=10, help="Number of results")
@click.option("--min-score", type=float, default=0.05, help="Minimum similarity score")
def search_cmd(input_json: Path, query: str, top_k: int, min_score: float) -> None:
    """Semantic search over enriched bookmarks."""
    results = search_from_file(input_json, query, top_k, min_score)
    if not results:
        click.echo("No results found.")
        return
    click.echo(f"\nTop {len(results)} results for: {query}\n")
    for i, bm in enumerate(results, 1):
        score = bm.get("search_score", 0)
        title = bm.get("title", "Untitled")
        url = bm.get("url", "")
        cat = " > ".join(bm.get("category_breadcrumbs", [])[-2:])
        click.echo(f"{i}. [{score}] {title}")
        click.echo(f"   URL: {url}")
        click.echo(f"   Cat: {cat}")
        click.echo()


# Register subgroups and sibling-module commands onto the top-level group.
cli.add_command(export)
cli.add_command(tag_graph)
cli.add_command(crosslinks)
cli.add_command(pipeline)
cli.add_command(config_cmd)
cli.add_command(migrate_db)
cli.add_command(db_status)
cli.add_command(serve_cmd)
cli.add_command(dashboard_cmd)
cli.add_command(git_push)


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
