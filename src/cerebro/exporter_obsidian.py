"""Export enriched bookmarks to Obsidian-ready markdown vault."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from src.cerebro.models import Bookmark
from src.cerebro.utils import ensure_dir, safe_filename

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


def _markdown_body(bookmark: Bookmark, related: list[tuple[Bookmark, str]]) -> str:
    """Build markdown body with dead link / duplicate / OG metadata."""
    lines = [
        f"# {bookmark.title}",
        "",
        f"> {bookmark.description}",
        "",
        "## Link",
        f"- [Open]({bookmark.url})",
    ]

    if bookmark.is_dead_link:
        status_str = str(bookmark.http_status) if bookmark.http_status else "unknown"
        lines.extend(
            [
                "",
                "> ⚠️ **Dead link detected** — HTTP status: " + status_str,
            ]
        )

    if bookmark.duplicate_group_id:
        lines.extend(
            [
                "",
                f"> 🔗 **Duplicate group:** `{bookmark.duplicate_group_id}`",
            ]
        )

    fm = bookmark.fetched_metadata
    if fm and not bookmark.is_dead_link:
        og_title = fm.get("og_title")
        og_image = fm.get("og_image")
        og_type = fm.get("og_type")
        if og_title or og_image or og_type:
            lines.extend(["", "## Fetched Metadata"])
            if og_title:
                lines.append(f"- **OG Title:** {og_title}")
            if og_type:
                lines.append(f"- **OG Type:** {og_type}")
            if og_image:
                lines.append(f"- **OG Image:** {og_image}")

    lines.extend(
        [
            "",
            "## Metadata",
            f"- **Domain:** `{bookmark.domain}`",
            f"- **Added:** {bookmark.add_date_iso or 'Unknown'}",
            f"- **Category:** {' > '.join(bookmark.category_breadcrumbs)}",
            f"- **Confidence:** {bookmark.confidence_score:.2f}",
        ]
    )

    if bookmark.duplicate_group_id:
        lines.append(f"- **Duplicate group:** `{bookmark.duplicate_group_id}`")

    lines.extend(["", "## Tags"])
    for tag in bookmark.tags:
        lines.append(f"- #{tag}")

    if related:
        lines.extend(["", "## Related Bookmarks"])
        for rel, reason in related:
            rel_path = "/".join(rel.category_breadcrumbs)
            lines.append(f"- [{rel.title}]({rel.safe_title}.md) — _{reason}_ — {rel_path}")

    if bookmark.icon:
        lines.extend(["", f"![Icon]({bookmark.icon})"])

    return "\n".join(lines)


def _related_label(bm: Bookmark, other: Bookmark) -> str:
    """Describe why two bookmarks are related."""
    if bm.category_path == other.category_path:
        return "Same category"
    if bm.domain and bm.domain == other.domain:
        return f"Same domain: {bm.domain}"
    if bm.add_date_epoch and other.add_date_epoch:
        return "Bookmarked together"
    return "Related"


def export_obsidian(
    bookmarks: list[Bookmark],
    vault_dir: Path | str,
    max_related: int = 5,
) -> Path:
    """Export bookmarks as Obsidian markdown vault."""
    vault_dir = ensure_dir(Path(vault_dir))
    logger.info(f"Exporting Obsidian vault to {vault_dir}")

    by_category: dict[str, list[Bookmark]] = {}
    by_domain: dict[str, list[Bookmark]] = {}
    for bm in bookmarks:
        path = bm.category_path
        by_category.setdefault(path, []).append(bm)
        if bm.domain:
            by_domain.setdefault(bm.domain, []).append(bm)

    count = 0
    total = len(bookmarks)
    for bm in bookmarks:
        safe_parts = [
            p for p in bm.category_breadcrumbs if p and p != ".." and not p.startswith("/")
        ]
        cat_dir = vault_dir / "/".join(safe_parts) if safe_parts else vault_dir
        ensure_dir(cat_dir)

        related: list[tuple[Bookmark, str]] = []
        related_ids: set[str] = set()
        for r in by_category.get(bm.category_path, []):
            if r.id != bm.id and r.id not in related_ids:
                related.append((r, "Same category"))
                related_ids.add(r.id)
        if bm.domain:
            for r in by_domain.get(bm.domain, []):
                if r.id != bm.id and r.id not in related_ids and len(related) < max_related * 2:
                    related.append((r, f"Same domain: {bm.domain}"))
                    related_ids.add(r.id)
        if bm.add_date_epoch:
            bm_epoch = int(bm.add_date_epoch) if bm.add_date_epoch else 0
            for r in bookmarks:
                if r.id != bm.id and r.id not in related_ids and r.add_date_epoch:
                    diff = abs(int(r.add_date_epoch) - bm_epoch)
                    if diff < 1800 and len(related) < max_related:
                        related.append((r, "Bookmarked together"))
                        related_ids.add(r.id)
        related = related[:max_related]

        front = _frontmatter(bm)
        body = _markdown_body(bm, related)

        yaml_block = yaml.dump(front, default_flow_style=False, allow_unicode=True, sort_keys=False)
        content = f"---\n{yaml_block}---\n\n{body}\n"

        file_path = cat_dir / f"{bm.safe_title}.md"
        if file_path.exists():
            file_path = cat_dir / f"{safe_filename(bm.title)}_{bm.id[:8]}.md"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        count += 1

        if count % 500 == 0:
            logger.info(f"Exported {count}/{total} markdown files")

    logger.info(f"Exported {count} markdown files to {vault_dir}")
    return vault_dir
