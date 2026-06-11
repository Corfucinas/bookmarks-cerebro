"""Export enriched bookmarks to Obsidian-ready markdown vault."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .models import Bookmark
from .utils import ensure_dir, safe_filename

logger = logging.getLogger("cerebro")


def _frontmatter(bookmark: Bookmark) -> dict[str, Any]:
    """Build YAML frontmatter dict."""
    return {
        "id": bookmark.id,
        "url": bookmark.url,
        "title": bookmark.title,
        "tags": bookmark.tags,
        "category": bookmark.category_path,
        "category_breadcrumbs": bookmark.category_breadcrumbs,
        "date_added": bookmark.add_date_iso,
        "domain": bookmark.domain,
        "confidence": round(bookmark.confidence_score, 2),
        "description_source": bookmark.description_source,
    }


def _markdown_body(bookmark: Bookmark, related: list[Bookmark]) -> str:
    """Build markdown body."""
    lines = [
        f"# {bookmark.title}",
        "",
        f"> {bookmark.description}",
        "",
        "## Link",
        f"- [Open]({bookmark.url})",
        "",
        "## Metadata",
        f"- **Domain:** `{bookmark.domain}`",
        f"- **Added:** {bookmark.add_date_iso or 'Unknown'}",
        f"- **Category:** {' > '.join(bookmark.category_breadcrumbs)}",
        f"- **Confidence:** {bookmark.confidence_score:.2f}",
        "",
        "## Tags",
    ]
    for tag in bookmark.tags:
        lines.append(f"- #{tag}")

    if related:
        lines.extend(["", "## Related Bookmarks"])
        for rel in related[:10]:
            rel_path = "/".join(rel.category_breadcrumbs)
            lines.append(f"- [{rel.title}]({rel.safe_title}.md) — {rel_path}")

    if bookmark.icon:
        lines.extend(["", f"![Icon]({bookmark.icon})"])

    return "\n".join(lines)


def export_obsidian(
    bookmarks: list[Bookmark],
    vault_dir: Path | str,
    max_related: int = 5,
) -> Path:
    """Export bookmarks as Obsidian markdown vault."""
    vault_dir = ensure_dir(Path(vault_dir))
    logger.info(f"Exporting Obsidian vault to {vault_dir}")

    # Group by category for related links
    by_category: dict[str, list[Bookmark]] = {}
    for bm in bookmarks:
        path = bm.category_path
        by_category.setdefault(path, []).append(bm)

    count = 0
    for bm in bookmarks:
        cat_dir = vault_dir / "/".join(bm.category_breadcrumbs)
        ensure_dir(cat_dir)

        # Find related bookmarks in same category
        related = [r for r in by_category.get(bm.category_path, []) if r.id != bm.id][:max_related]

        front = _frontmatter(bm)
        body = _markdown_body(bm, related)

        # YAML frontmatter block
        yaml_block = yaml.dump(front, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = f"---\n{yaml_block}---\n\n{body}\n"

        file_path = cat_dir / f"{bm.safe_title}.md"
        # Handle duplicates
        if file_path.exists():
            file_path = cat_dir / f"{safe_filename(bm.title)}_{bm.id[:8]}.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        count += 1

        if count % 500 == 0:
            logger.info(f"Exported {count}/{len(bookmarks)} markdown files")

    logger.info(f"Exported {count} markdown files to {vault_dir}")
    return vault_dir
