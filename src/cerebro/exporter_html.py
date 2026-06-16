"""Export enriched bookmarks to Netscape Bookmark HTML."""

from __future__ import annotations

import html
import logging
from pathlib import Path
from typing import Any

from src.cerebro.models import Bookmark
from src.cerebro.utils import ensure_dir

logger = logging.getLogger("cerebro")

HTML_TEMPLATE = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
{body}
</DL><p>
"""


def _build_folder_html(name: str, children_html: str, indent: int = 1) -> str:
    """Build HTML for a folder node."""
    prefix = "    " * indent
    lines = [
        f"{prefix}<DT><H3>{html.escape(name)}</H3>",
        f"{prefix}<DL><p>",
    ]
    lines.append(children_html)
    lines.append(f"{prefix}</DL><p>")
    return "\n".join(lines)


def _build_link_html(bookmark: Bookmark, indent: int = 1) -> str:
    """Build HTML for a bookmark link."""
    prefix = "    " * indent
    attrs = [f'HREF="{html.escape(bookmark.url)}"']
    if bookmark.add_date_epoch:
        attrs.append(f'ADD_DATE="{bookmark.add_date_epoch}"')
    if bookmark.icon:
        attrs.append(f'ICON="{html.escape(bookmark.icon)}"')
    attr_str = " ".join(attrs)
    return f"{prefix}<DT><A {attr_str}>{html.escape(bookmark.title)}</A>"


def _build_taxonomy_tree(bookmarks: list[Bookmark]) -> dict[str, Any]:
    """Build nested dict tree from category breadcrumbs."""
    tree: dict[str, Any] = {}
    for bm in bookmarks:
        node = tree
        for crumb in bm.category_breadcrumbs:
            if crumb not in node:
                node[crumb] = {}
            node = node[crumb]
        # Store bookmark in leaf
        if "__bookmarks__" not in node:
            node["__bookmarks__"] = []
        node["__bookmarks__"].append(bm)
    return tree


def _tree_to_html(tree: dict[str, Any], indent: int = 1) -> str:
    """Convert tree dict to Netscape HTML."""
    lines = []
    # Sort for determinism
    for key in sorted(tree.keys()):
        if key == "__bookmarks__":
            continue
        value = tree[key]
        if isinstance(value, dict):
            children_html = _tree_to_html(value, indent + 1)
            # Add bookmarks in this folder
            if "__bookmarks__" in value:
                bm_lines = [_build_link_html(bm, indent + 1) for bm in value["__bookmarks__"]]
                if children_html:
                    children_html = "\n".join([*bm_lines, children_html])
                else:
                    children_html = "\n".join(bm_lines)
            lines.append(_build_folder_html(key, children_html, indent))
    return "\n".join(lines)


def export_html(bookmarks: list[Bookmark], output_path: Path | str) -> Path:
    """Export bookmarks to Netscape Bookmark HTML."""
    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    tree = _build_taxonomy_tree(bookmarks)
    body = _tree_to_html(tree)

    # Add root-level bookmarks
    if "__bookmarks__" in tree:
        root_bms = "\n".join(_build_link_html(bm, 1) for bm in tree["__bookmarks__"])
        body = root_bms + "\n" + body if body else root_bms

    html_content = HTML_TEMPLATE.format(body=body)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Exported {len(bookmarks)} bookmarks to {output_path}")
    return output_path
