"""CLI entrypoint for Bookmarks Cerebro."""

from __future__ import annotations

import logging
from pathlib import Path

import click

from src.cerebro import __version__
from src.cerebro.classifier import classify_bookmarks
from src.cerebro.crosslinks import find_crosslinks
from src.cerebro.dedup import detect_duplicates
from src.cerebro.enricher import enrich_bookmarks
from src.cerebro.exporter_csv import export_csv
from src.cerebro.exporter_html import export_html
from src.cerebro.exporter_json import export_json
from src.cerebro.exporter_jsonl import export_jsonl
from src.cerebro.exporter_obsidian import export_obsidian
from src.cerebro.fetcher import fetch_bookmarks
from src.cerebro.parser import parse_bookmarks
from src.cerebro.search import search_from_file
from src.cerebro.server import run_server
from src.cerebro.utils import setup_logging

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
    from src.cerebro.utils import save_json

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
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    from src.cerebro.models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = classify_bookmarks(bookmarks, taxonomy, train_ml=not no_ml)
    from src.cerebro.utils import save_json

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
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    from src.cerebro.models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = enrich_bookmarks(bookmarks)
    from src.cerebro.utils import save_json

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
    from src.cerebro.models import Bookmark
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = detect_duplicates(bookmarks, mode=mode, similarity_threshold=threshold)
    from src.cerebro.utils import save_json

    save_json(output, [bm.to_dict() for bm in bookmarks])
    groups = {bm.duplicate_group_id for bm in bookmarks if bm.duplicate_group_id}
    click.echo(f"✓ Deduped ({mode}): {len(groups)} groups → {output}")


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
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    from src.cerebro.models import Bookmark

    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_json(bookmarks, output)
    click.echo(f"✓ Exported JSON → {output}")


@export.command("obsidian")
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option("--vault-dir", "-d", type=click.Path(path_type=Path), default="data/vault")
def export_obsidian_cmd(input_json: Path, vault_dir: Path) -> None:
    """Export to Obsidian markdown vault."""
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    from src.cerebro.models import Bookmark

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
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    from src.cerebro.models import Bookmark

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
    from src.cerebro.models import Bookmark
    from src.cerebro.utils import load_json

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
    from src.cerebro.models import Bookmark
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    export_csv(bookmarks, output)
    click.echo(f"✓ Exported CSV → {output}")


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


@cli.command()
@click.option("--host", type=str, default="127.0.0.1", help="Server host")
@click.option("--port", type=int, default=8765, help="Server port")
def serve(host: str, port: int) -> None:
    """Start local HTTP server for browser-extension ingestion."""
    run_server(host, port)


@cli.command()
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


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="output/tag_graph.gexf",
    help="Output GEXF file",
)
def tag_graph(input_json: Path, output: Path) -> None:
    """Build tag co-occurrence graph and export to GEXF."""
    import itertools

    from src.cerebro.utils import load_json

    data = load_json(input_json)
    bookmarks = data.get("bookmarks", []) if isinstance(data, dict) else data

    # Build co-occurrence edges
    edges: dict[tuple[str, str], int] = {}
    for bm in bookmarks:
        tags = bm.get("tags", [])
        for a, b in itertools.combinations(sorted(set(tags)), 2):
            key = (a, b)
            edges[key] = edges.get(key, 0) + 1

    # Write GEXF
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    nodes = sorted({t for pair in edges for t in pair})
    with open(output, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n')
        f.write('  <graph mode="static" defaultedgetype="undirected">\n')
        f.write(f'    <nodes count="{len(nodes)}">\n')
        for node in nodes:
            f.write(f'      <node id="{node}" label="{node}" />\n')
        f.write("    </nodes>\n")
        f.write(f'    <edges count="{len(edges)}">\n')
        for (a, b), w in sorted(edges.items()):
            f.write(f'      <edge source="{a}" target="{b}" weight="{w}" />\n')
        f.write("    </edges>\n")
        f.write("  </graph>\n")
        f.write("</gexf>\n")

    click.echo(f"✓ Tag graph exported: {output} ({len(nodes)} nodes, {len(edges)} edges)")


@cli.command()
@click.argument("input_json", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default="data/processed/crosslinked_bookmarks.json",
)
@click.option(
    "--export-format",
    "-f",
    type=click.Choice(["json", "gexf"], case_sensitive=False),
    default="json",
    help="Export format for cross-links",
)
def crosslinks(input_json: Path, output: Path, export_format: str) -> None:
    """Find cross-links between bookmarks and export relations."""
    from src.cerebro.models import Bookmark
    from src.cerebro.utils import load_json

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = find_crosslinks(bookmarks)
    from src.cerebro.utils import save_json

    save_json(output, [bm.to_dict() for bm in bookmarks])
    total = sum(len(bm.related_ids) for bm in bookmarks)
    click.echo(f"✓ Cross-links: {total} relations → {output}")

    if export_format == "gexf":
        gexf_path = output.with_suffix(".gexf")
        with open(gexf_path, "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            f.write('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n')
            f.write('  <graph mode="static" defaultedgetype="directed">\n')
            nodes = {bm.id: bm.title for bm in bookmarks}
            f.write(f'    <nodes count="{len(nodes)}">\n')
            for nid, label in nodes.items():
                f.write(f'      <node id="{nid}" label="{label}" />\n')
            f.write("    </nodes>\n")
            edges = []
            for bm in bookmarks:
                for rid in bm.related_ids:
                    edges.append((bm.id, rid))
            f.write(f'    <edges count="{len(edges)}">\n')
            for src, tgt in edges:
                f.write(f'      <edge source="{src}" target="{tgt}" />\n')
            f.write("    </edges>\n")
            f.write("  </graph>\n")
            f.write("</gexf>\n")
        click.echo(f"✓ Cross-link GEXF → {gexf_path}")


def main() -> None:
    cli()


if __name__ == "__main__":
    main()
