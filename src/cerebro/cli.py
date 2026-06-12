"""CLI entrypoint for Bookmarks Cerebro."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from . import __version__
from .classifier import classify_bookmarks
from .dedup import detect_duplicates
from .enricher import enrich_bookmarks
from .exporter_html import export_html
from .exporter_json import export_json
from .exporter_obsidian import export_obsidian
from .fetcher import fetch_bookmarks
from .parser import parse_bookmarks
from .utils import setup_logging

logger = logging.getLogger("cerebro")


@click.group()
@click.version_option(version=__version__, prog_name="cerebro")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def cli(verbose: bool) -> None:
    """Bookmarks Cerebro — parse, categorize, enrich, and export bookmarks."""
    level = logging.DEBUG if verbose else logging.INFO
    setup_logging(level)


@cli.command()
@click.argument("input_html", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default="data/processed/raw_bookmarks.json"
)
def parse(input_html: Path, output: Path) -> None:
    """Parse Netscape Bookmark HTML to raw JSON."""
    bookmarks = parse_bookmarks(input_html)
    from .utils import save_json

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
    from .utils import load_json

    data = load_json(input_json)
    from .models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = classify_bookmarks(bookmarks, taxonomy, train_ml=not no_ml)
    from .utils import save_json

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
    from .utils import load_json

    data = load_json(input_json)
    from .models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = enrich_bookmarks(bookmarks)
    from .utils import save_json

    save_json(output, [bm.to_dict() for bm in bookmarks])
    click.echo(f"✓ Enriched {len(bookmarks)} bookmarks → {output}")


@cli.group()
def export() -> None:
    """Export bookmarks to various formats."""
    pass


@export.command("json")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/enriched_bookmarks.json",
)
def export_json_cmd(input_json: Path, output: Path) -> None:
    """Export to JSON."""
    from .utils import load_json

    data = load_json(input_json)
    from .models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_json(bookmarks, output)
    click.echo(f"✓ Exported JSON → {output}")


@export.command("obsidian")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option("--vault-dir", "-d", type=click.Path(path_type=Path), default="data/vault")
def export_obsidian_cmd(input_json: Path, vault_dir: Path) -> None:
    """Export to Obsidian markdown vault."""
    from .utils import load_json

    data = load_json(input_json)
    from .models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_obsidian(bookmarks, vault_dir)
    click.echo(f"✓ Exported Obsidian vault → {vault_dir}")


@export.command("html")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/bookmarks_cerebro.html",
)
def export_html_cmd(input_json: Path, output: Path) -> None:
    """Export to Netscape Bookmark HTML."""
    from .utils import load_json

    data = load_json(input_json)
    from .models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_html(bookmarks, output)
    click.echo(f"✓ Exported HTML → {output}")


@cli.command()
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
def pipeline(
    input_html: Path,
    taxonomy: Path,
    output_dir: Path,
    no_ml: bool,
    check_dead: bool,
    fetch_live: bool,
    fetch_workers: int,
    fetch_timeout: int,
) -> None:
    """Run full pipeline: parse → classify → dedup → [fetch] → enrich → export."""
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


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
