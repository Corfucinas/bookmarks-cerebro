"""Export Click group and subcommands for Bookmarks Cerebro CLI."""

from __future__ import annotations

from pathlib import Path

import click

from src.cerebro.exporter_csv import export_csv
from src.cerebro.exporter_html import export_html
from src.cerebro.exporter_json import export_json
from src.cerebro.exporter_jsonl import export_jsonl
from src.cerebro.exporter_obsidian import export_obsidian
from src.cerebro.models import Bookmark
from src.cerebro.utils import load_json


@click.group()
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

    data = load_json(input_json)

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_json(bookmarks, output)
    click.echo(f"✓ Exported JSON → {output}")


@export.command("obsidian")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option("--vault-dir", "-d", type=click.Path(path_type=Path), default="data/vault")
def export_obsidian_cmd(input_json: Path, vault_dir: Path) -> None:
    """Export to Obsidian markdown vault."""

    data = load_json(input_json)

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

    data = load_json(input_json)

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_html(bookmarks, output)
    click.echo(f"✓ Exported HTML → {output}")


@export.command("jsonl")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default="data/processed/bookmarks.jsonl"
)
def export_jsonl_cmd(input_json: Path, output: Path) -> None:
    """Export to JSONL (one JSON object per line)."""

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_jsonl(bookmarks, output)
    click.echo(f"✓ Exported JSONL → {output}")


@export.command("csv")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o", type=click.Path(path_type=Path), default="data/processed/bookmarks.csv"
)
def export_csv_cmd(input_json: Path, output: Path) -> None:
    """Export to CSV."""

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_csv(bookmarks, output)
    click.echo(f"✓ Exported CSV → {output}")
