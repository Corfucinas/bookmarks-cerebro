"""Pipeline CLI command for Bookmarks Cerebro.

Orchestrates parse → classify → dedup → [fetch] → enrich → [export/db].
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from src.cerebro.classifier import classify_bookmarks
from src.cerebro.db import count_bookmarks, get_session, save_bookmarks
from src.cerebro.dedup import detect_duplicates
from src.cerebro.enricher import enrich_bookmarks
from src.cerebro.exporter_html import export_html
from src.cerebro.exporter_json import export_json
from src.cerebro.exporter_obsidian import export_obsidian
from src.cerebro.fetcher import fetch_bookmarks
from src.cerebro.parser import parse_bookmarks


@click.command()
@click.argument("input_html", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--taxonomy", "-t", type=click.Path(exists=True, path_type=Path), default="taxonomy.yaml"
)
@click.option("--output-dir", "-d", type=click.Path(path_type=Path), default="data")
@click.option("--no-ml", is_flag=True, help="Skip ML fallback classification")
@click.option("--check-dead", is_flag=True, help="Fetch all pages and flag dead links")
@click.option("--fetch-live", is_flag=True, help="Fetch live page metadata (title, OG tags)")
@click.option("--fetch-workers", type=int, default=20, help="Parallel fetch workers")
@click.option("--fetch-timeout", type=int, default=15, help="Fetch timeout per page")
@click.option("--to-db", is_flag=True, help="Persist enriched bookmarks to SQLite database")
@click.pass_obj
def pipeline(
    obj: dict[str, Any],
    input_html: Path,
    taxonomy: Path,
    output_dir: Path,
    no_ml: bool,
    check_dead: bool,
    fetch_live: bool,
    fetch_workers: int,
    fetch_timeout: int,
    to_db: bool,
) -> None:
    """Run full pipeline: parse → classify → dedup → [fetch] → enrich → [export/db]."""
    output_dir.mkdir(parents=True, exist_ok=True)

    click.echo("📖 Parsing...")
    bookmarks = parse_bookmarks(input_html)

    click.echo("🧠 Classifying...")
    bookmarks = classify_bookmarks(bookmarks, taxonomy, train_ml=not no_ml)

    click.echo("🔍 Detecting duplicates...")
    bookmarks = detect_duplicates(bookmarks)

    if check_dead or fetch_live:
        click.echo("🌐 Fetching live pages..." if fetch_live else "💀 Checking for dead links...")
        bookmarks = fetch_bookmarks(bookmarks, max_workers=fetch_workers, timeout=fetch_timeout)

    click.echo("🏷️ Enriching...")
    bookmarks = enrich_bookmarks(bookmarks)

    if to_db:
        click.echo("💾 Persisting to SQLite...")
        settings = obj["settings"]
        with get_session(settings.db_url) as session:
            count = save_bookmarks(session, bookmarks)
            total = count_bookmarks(session)
        click.echo(f"✓ Saved {count} bookmarks to database (total {total})")

    click.echo("📤 Exporting...")
    enriched_json = output_dir / "processed" / "enriched_bookmarks.json"
    enriched_json.parent.mkdir(parents=True, exist_ok=True)
    export_json(bookmarks, enriched_json)

    vault_dir = output_dir / "vault"
    export_obsidian(bookmarks, vault_dir)

    html_output = output_dir / "processed" / "bookmarks_cerebro.html"
    export_html(bookmarks, html_output)

    click.echo("\n✅ Pipeline complete!")
    click.echo(f"   JSON:  {enriched_json}")
    click.echo(f"   Vault: {vault_dir}")
    click.echo(f"   HTML:  {html_output}")
    if to_db:
        settings = obj["settings"]
        click.echo(f"   DB:    {settings.database.path}")
