"""Graph-related CLI commands for Bookmarks Cerebro.

Houses the `tag_graph` and `crosslinks` subcommands plus the shared
`_write_gexf` helper that emits a minimal GEXF 1.2 graph file.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable
from pathlib import Path

import click

from src.cerebro.crosslinks import find_crosslinks
from src.cerebro.models import Bookmark
from src.cerebro.utils import load_json, save_json


def _write_gexf(
    path: Path,
    nodes: dict[str, str],
    edges: Iterable[tuple[str, str] | tuple[str, str, float | int]],
    directed: bool,
) -> None:
    """Write a minimal GEXF 1.2 graph file.

    Args:
        path: output file path (parent directories are created).
        nodes: mapping of node id to node label.
        edges: iterable of (source, target) or (source, target, weight).
        directed: whether the graph is directed (undirected otherwise).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    edge_type = "directed" if directed else "undirected"
    edge_list: list[tuple[str, str, str | None]] = []
    for raw in edges:
        if len(raw) == 3:
            src, tgt, w = raw
            edge_list.append((src, tgt, str(w)))
        else:
            src, tgt = raw
            edge_list.append((src, tgt, None))

    with open(path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">\n')
        f.write(f'  <graph mode="static" defaultedgetype="{edge_type}">\n')
        f.write(f'    <nodes count="{len(nodes)}">\n')
        for nid, label in nodes.items():
            f.write(f'      <node id="{nid}" label="{label}" />\n')
        f.write("    </nodes>\n")
        f.write(f'    <edges count="{len(edge_list)}">\n')
        for src, tgt, weight in edge_list:
            if weight is not None:
                f.write(f'      <edge source="{src}" target="{tgt}" weight="{weight}" />\n')
            else:
                f.write(f'      <edge source="{src}" target="{tgt}" />\n')
        f.write("    </edges>\n")
        f.write("  </graph>\n")
        f.write("</gexf>\n")


@click.command()
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

    data = load_json(input_json)
    bookmarks = data.get("bookmarks", []) if isinstance(data, dict) else data

    # Build co-occurrence edges
    edges: dict[tuple[str, str], int] = {}
    for bm in bookmarks:
        tags = bm.get("tags", [])
        for a, b in itertools.combinations(sorted(set(tags)), 2):
            key = (a, b)
            edges[key] = edges.get(key, 0) + 1

    nodes = {t: t for t in sorted({t for pair in edges for t in pair})}
    _write_gexf(output, nodes, [(a, b, w) for (a, b), w in sorted(edges.items())], directed=False)

    click.echo(f"✓ Tag graph exported: {output} ({len(nodes)} nodes, {len(edges)} edges)")


@click.command()
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

    data = load_json(input_json)
    bookmarks = [Bookmark.from_dict(d) for d in data]
    bookmarks = find_crosslinks(bookmarks)

    save_json(output, [bm.to_dict() for bm in bookmarks])
    total = sum(len(bm.related_ids) for bm in bookmarks)
    click.echo(f"✓ Cross-links: {total} relations → {output}")

    if export_format == "gexf":
        gexf_path = output.with_suffix(".gexf")
        nodes = {bm.id: bm.title for bm in bookmarks}
        edge_iter: Iterable[tuple[str, str]] = (
            (bm.id, rid) for bm in bookmarks for rid in bm.related_ids
        )
        _write_gexf(gexf_path, nodes, edge_iter, directed=True)
        click.echo(f"✓ Cross-link GEXF → {gexf_path}")
