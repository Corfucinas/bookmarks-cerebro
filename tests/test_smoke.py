"""Minimal smoke tests for cerebro modules."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.crosslinks import find_crosslinks
from cerebro.dedup import detect_duplicates
from cerebro.exporter_csv import export_csv
from cerebro.exporter_html import export_html
from cerebro.exporter_json import export_json
from cerebro.exporter_jsonl import export_jsonl
from cerebro.exporter_obsidian import export_obsidian
from cerebro.fetcher import _is_soft_dead
from cerebro.models import Bookmark
from cerebro.parser import parse_bookmarks
from cerebro.search import build_index, search


def test_models():
    b = Bookmark(id="test-1", title="Test", url="https://example.com", is_dead_link=False)
    assert b.title == "Test"
    assert b.url == "https://example.com"


def test_parser_roundtrip():
    bookmarks = parse_bookmarks(".github/testdata/sample.html")
    assert len(bookmarks) > 0


def test_dedup():
    b1 = Bookmark(id="a", title="A", url="https://example.com/page")
    b2 = Bookmark(id="b", title="A", url="https://example.com/page")
    b3 = Bookmark(id="c", title="B", url="https://example.com/other")
    deduped = detect_duplicates([b1, b2, b3])
    assert len(deduped) == 3  # marks duplicates, does not remove


def test_fetcher_utilities():
    assert _is_soft_dead(403) is True
    assert _is_soft_dead(200) is False


def test_search_build_index():
    bookmarks = [
        {
            "title": "Python tutorial",
            "url": "https://python.org",
            "tags": ["python"],
            "description": "",
            "category_breadcrumbs": [],
            "domain": "python.org",
        },
        {
            "title": "Rust book",
            "url": "https://rust-lang.org",
            "tags": ["rust"],
            "description": "",
            "category_breadcrumbs": [],
            "domain": "rust-lang.org",
        },
    ]
    vectorizer, matrix, bms = build_index(bookmarks)
    results = search("python", vectorizer, matrix, bms, top_k=2)
    assert len(results) > 0


def test_exporter_json():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_json(bookmarks, "/tmp/test_cerebro.json")
    assert path.exists()
    parsed = json.loads(path.read_text())
    assert len(parsed) == 1


def test_exporter_html():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_html(bookmarks, "/tmp/test_cerebro.html")
    assert "https://x.com" in path.read_text()


def test_exporter_csv():
    bookmarks = [Bookmark(id="t1", title="T", url="https://x.com")]
    path = export_csv(bookmarks, "/tmp/test_cerebro.csv")
    assert path.exists()
    text = path.read_text()
    assert "id,title,url" in text
    assert "https://x.com" in text


def test_exporter_jsonl():
    b1 = Bookmark(
        id="a", title="A", url="https://example.com/1", domain="example.com", tags=["python", "ml"]
    )
    b2 = Bookmark(
        id="b",
        title="B",
        url="https://example.com/2",
        domain="example.com",
        tags=["python", "ml", "rust"],
    )
    b3 = Bookmark(id="c", title="C", url="https://other.com/3", domain="other.com", tags=["games"])
    path = export_jsonl([b1, b2, b3], "/tmp/test_cerebro.jsonl")
    assert path.exists()
    lines = path.read_text().strip().split("\n")
    assert len(lines) == 3
    parsed = json.loads(lines[0])
    assert parsed["url"] == "https://example.com/1"


def test_crosslinks():
    b1 = Bookmark(
        id="a", title="A", url="https://example.com/1", domain="example.com", tags=["python", "ml"]
    )
    b2 = Bookmark(
        id="b",
        title="B",
        url="https://example.com/2",
        domain="example.com",
        tags=["python", "ml", "rust"],
    )
    b3 = Bookmark(id="c", title="C", url="https://other.com/3", domain="other.com", tags=["games"])
    bookmarks = find_crosslinks([b1, b2, b3])
    # b1 and b2 share domain, so they should be related via domain match
    assert any(len(bm.related_ids) > 0 for bm in bookmarks)


def test_export_obsidian_path_traversal(tmp_path: Path) -> None:
    """Path traversal via category_breadcrumbs must not escape vault_dir."""
    # Arrange - malicious breadcrumbs intended to escape vault
    bm = Bookmark(
        id="evil-1",
        title="Evil",
        url="https://example.com/evil",
        category_breadcrumbs=["..", "..", "tmp", "evil"],
    )
    vault_dir = tmp_path / "vault"
    traversal_target = tmp_path.parent.parent / "tmp" / "evil"

    # Act
    export_obsidian([bm], vault_dir)

    # Assert - no file written outside vault
    assert not traversal_target.exists(), f"Path traversal: {traversal_target} should not exist"
    # The bookmark should still be written somewhere inside vault_dir
    md_files = list(vault_dir.rglob("*.md"))
    assert len(md_files) == 1, f"Expected 1 markdown in vault, got {len(md_files)}"
    # Ensure written file is actually inside vault_dir
    assert md_files[0].resolve().is_relative_to(vault_dir.resolve())


def test_export_obsidian_no_mutation(tmp_path):
    """export_obsidian must not mutate input bookmarks' related_ids."""
    from cerebro.exporter_obsidian import export_obsidian

    b1 = Bookmark(id="a", title="Alpha", url="https://example.com/alpha", domain="example.com")
    b2 = Bookmark(id="b", title="Beta", url="https://example.com/beta", domain="example.com")
    bookmarks = [b1, b2]
    assert b1.related_ids == []
    assert b2.related_ids == []

    export_obsidian(bookmarks, tmp_path / "vault")

    assert b1.related_ids == [], f"Input mutated: {b1.related_ids}"
    assert b2.related_ids == [], f"Input mutated: {b2.related_ids}"


def test_export_obsidian_with_related_ids_section(tmp_path: Path) -> None:
    """Related bookmarks section appears in markdown when related_ids set."""
    b1 = Bookmark(
        id="rel1",
        title="Alpha",
        url="https://example.com/alpha",
        domain="example.com",
        category_breadcrumbs=["Programming", "Python"],
    )
    b2 = Bookmark(
        id="rel2",
        title="Beta",
        url="https://example.com/beta",
        domain="example.com",
        category_breadcrumbs=["Programming", "Python"],
    )
    b1.related_ids = ["rel2"]

    vault = tmp_path / "vault"
    export_obsidian([b1, b2], vault)

    md_files = list(vault.rglob("*.md"))
    assert len(md_files) == 2
    alpha = next(f for f in md_files if "Alpha" in f.name)
    content = alpha.read_text()
    assert "## Related Bookmarks" in content
    assert "Beta" in content


def test_export_obsidian_tags_in_frontmatter(tmp_path: Path) -> None:
    """Tags appear in YAML frontmatter."""
    bm = Bookmark(
        id="tags1",
        title="Tagged",
        url="https://example.com/tagged",
        domain="example.com",
        tags=["python", "async", "testing"],
        category_breadcrumbs=["Programming", "Python"],
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    md = next((tmp_path / "vault").rglob("*.md"))
    content = md.read_text()
    fm = content.split("---")[1]
    assert "tags:" in fm
    assert "python" in fm
    assert "async" in fm
    assert "testing" in fm


def test_export_obsidian_empty_title_fallback(tmp_path: Path) -> None:
    """Bookmark with empty title falls back to 'untitled' filename."""
    bm = Bookmark(
        id="empty-title",
        title="",
        url="https://example.com/empty-title-page",
        domain="example.com",
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    md_files = list(vault.rglob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].name == "untitled.md"
    content = md_files[0].read_text()
    assert "https://example.com/empty-title-page" in content


def test_export_obsidian_special_chars_in_category(tmp_path: Path) -> None:
    """Category with special characters creates a sanitized directory."""
    bm = Bookmark(
        id="special-cat",
        title="Special",
        url="https://example.com/special",
        domain="example.com",
        category_breadcrumbs=["Programming / Languages: Python"],
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    md_files = list(vault.rglob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].resolve().is_relative_to(vault.resolve())


def test_export_obsidian_nested_categories(tmp_path: Path) -> None:
    """Deeply nested breadcrumbs produce nested directory structure."""
    bm = Bookmark(
        id="nested-1",
        title="Nested",
        url="https://example.com/nested",
        domain="example.com",
        category_breadcrumbs=["Programming", "Languages", "Python", "Async"],
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    expected_dir = vault / "Programming" / "Languages" / "Python" / "Async"
    assert expected_dir.is_dir(), f"Expected nested dir at {expected_dir}"
    md_files = list(expected_dir.glob("*.md"))
    assert len(md_files) == 1
    assert md_files[0].stem == "Nested"


def test_export_obsidian_dead_link_warning(tmp_path: Path) -> None:
    """Dead link bookmark produces a warning section in markdown."""
    bm = Bookmark(
        id="dead-link",
        title="Dead",
        url="https://example.com/dead",
        domain="example.com",
        is_dead_link=True,
        http_status=404,
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    content = next((tmp_path / "vault").rglob("*.md")).read_text()
    assert "Dead link detected" in content
    assert "404" in content


def test_export_obsidian_duplicate_group_in_body(tmp_path: Path) -> None:
    """Duplicate group ID appears in body and frontmatter."""
    bm = Bookmark(
        id="dup-1",
        title="Duplicate",
        url="https://example.com/dup",
        domain="example.com",
        duplicate_group_id="group-alpha",
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    content = next((tmp_path / "vault").rglob("*.md")).read_text()
    assert "Duplicate group" in content
    assert "group-alpha" in content


def test_export_obsidian_fetched_metadata_section(tmp_path: Path) -> None:
    """OG metadata appears in Fetched Metadata section when present."""
    bm = Bookmark(
        id="fm-1",
        title="Fetched",
        url="https://example.com/fetched",
        domain="example.com",
        fetched_metadata={
            "og_title": "OG Title",
            "og_image": "https://example.com/img.png",
            "og_type": "article",
        },
    )
    vault = tmp_path / "vault"
    export_obsidian([bm], vault)

    content = next((tmp_path / "vault").rglob("*.md")).read_text()
    assert "## Fetched Metadata" in content
    assert "OG Title" in content
    assert "article" in content
    assert "img.png" in content


def test_export_obsidian_bookmarked_together_related(tmp_path: Path) -> None:
    """Two bookmarks added within 1800s are related as 'Bookmarked together'."""
    b1 = Bookmark(
        id="together1",
        title="First",
        url="https://other.com/first",
        domain="other.com",
        add_date_epoch="1000000",
    )
    b2 = Bookmark(
        id="together2",
        title="Second",
        url="https://different.com/second",
        domain="different.com",
        add_date_epoch="1000100",
    )
    vault = tmp_path / "vault"
    export_obsidian([b1, b2], vault)

    first_md = next((tmp_path / "vault").rglob("First.md"))
    content = first_md.read_text()
    assert "## Related Bookmarks" in content
    # Different domains, same Uncategorized category -> "Same category" label wins.
    assert "Second" in content


def test_export_obsidian_related_label_same_domain(tmp_path: Path) -> None:
    """_related_label returns 'Same domain' label when domains match."""
    from cerebro.exporter_obsidian import _related_label

    b1 = Bookmark(
        id="d1", title="A", url="https://ex.com/a", domain="ex.com", category_breadcrumbs=["Cat1"]
    )
    b2 = Bookmark(
        id="d2", title="B", url="https://ex.com/b", domain="ex.com", category_breadcrumbs=["Cat2"]
    )
    label = _related_label(b1, b2)
    assert label == "Same domain: ex.com"


def test_export_obsidian_related_label_default(tmp_path: Path) -> None:
    """_related_label returns 'Related' when no specific match applies."""
    from cerebro.exporter_obsidian import _related_label

    b1 = Bookmark(
        id="x1",
        title="A",
        url="https://ex.com/a",
        domain="ex.com",
        category_breadcrumbs=["Cat1"],
        add_date_epoch="100",
    )
    b2 = Bookmark(
        id="x2",
        title="B",
        url="https://other.com/b",
        domain="other.com",
        category_breadcrumbs=["Cat2"],
    )  # no add_date_epoch
    label = _related_label(b1, b2)
    assert label == "Related"


def test_export_obsidian_dedup_filename_collision(tmp_path: Path) -> None:
    """Two bookmarks with same title in same category get unique filenames."""
    b1 = Bookmark(
        id="coll-1",
        title="Collision",
        url="https://example.com/a",
        domain="example.com",
        category_breadcrumbs=["Cat"],
    )
    b2 = Bookmark(
        id="coll-2",
        title="Collision",
        url="https://example.com/b",
        domain="example.com",
        category_breadcrumbs=["Cat"],
    )
    vault = tmp_path / "vault"
    export_obsidian([b1, b2], vault)

    md_files = list((vault / "Cat").glob("*.md"))
    assert len(md_files) == 2
    names = {f.name for f in md_files}
    assert "Collision.md" in names
