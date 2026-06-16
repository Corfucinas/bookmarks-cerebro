"""Behavior-lock regression tests for cerebro.fetcher.

Pins current behavior of _fetch_page, _is_dead, _is_soft_dead, and _extract_og_tags.
Uses unittest.mock.patch to mock urllib.request.urlopen — no real network calls.
"""

import sys
import urllib.error
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.fetcher import (
    DEAD_STATUSES,
    SOFT_DEAD_STATUSES,
    _extract_og_tags,
    _fetch_page,
    _is_dead,
    _is_soft_dead,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_head_mock(status: int, content_type: str = "text/html; charset=utf-8") -> MagicMock:
    """Return a MagicMock simulating a successful HEAD response."""
    m = MagicMock()
    m.getcode.return_value = status
    m.headers = {"Content-Type": content_type}
    return m


def _make_get_mock(
    status: int,
    html: bytes,
    content_type: str = "text/html; charset=utf-8",
) -> MagicMock:
    """Return a MagicMock simulating a successful GET response with body."""
    m = MagicMock()
    m.getcode.return_value = status
    m.headers = {"Content-Type": content_type}
    m.read.return_value = html
    return m


def _make_http_error(code: int) -> urllib.error.HTTPError:
    """Return an HTTPError that _fetch_head / _fetch_get will catch and return."""
    return urllib.error.HTTPError(
        url="http://example.com",
        code=code,
        msg="Error",
        hdrs={"Content-Type": "text/html"},
        fp=BytesIO(b""),
    )


# Minimal valid HTML used in successful-fetch tests
MINIMAL_HTML = (
    b"<html><head>"
    b"<title>Page Title</title>"
    b'<meta property="og:title" content="OG Title">'
    b'<meta property="og:description" content="OG Description">'
    b'<meta property="og:image" content="https://example.com/img.png">'
    b'<meta property="og:type" content="article">'
    b'<link rel="canonical" href="https://example.com/canonical">'
    b"</head><body><p>Hello</p></body></html>"
)

HTML_WITH_META_DESC = (
    b"<html><head>"
    b"<title>Page Title</title>"
    b'<meta name="description" content="Meta fallback description">'
    b"</head><body></body></html>"
)


# ---------------------------------------------------------------------------
# _is_dead
# ---------------------------------------------------------------------------


def test_is_dead_known_dead_statuses():
    """Every status in DEAD_STATUSES returns True."""
    for s in DEAD_STATUSES:
        assert _is_dead(s) is True, f"Expected True for status {s}"


def test_is_dead_none_returns_true():
    """None (connection failure) is treated as dead."""
    assert _is_dead(None) is True


def test_is_dead_alive_statuses():
    """200, 301, 302 are not dead."""
    for s in (200, 301, 302):
        assert _is_dead(s) is False, f"Expected False for status {s}"


# ---------------------------------------------------------------------------
# _is_soft_dead
# ---------------------------------------------------------------------------


def test_is_soft_dead_known_statuses():
    """Every status in SOFT_DEAD_STATUSES returns True."""
    for s in SOFT_DEAD_STATUSES:
        assert _is_soft_dead(s) is True, f"Expected True for status {s}"


def test_is_soft_dead_none_returns_false():
    """None is not soft-dead."""
    assert _is_soft_dead(None) is False


def test_is_soft_dead_alive_statuses():
    """200, 404 are not soft-dead."""
    assert _is_soft_dead(200) is False
    assert _is_soft_dead(404) is False


# ---------------------------------------------------------------------------
# _extract_og_tags
# ---------------------------------------------------------------------------


def test_extract_og_tags_all_fields():
    """Extracts og:title, og:description, og:image, og:type from meta tags."""
    soup = BeautifulSoup(MINIMAL_HTML, "html.parser")
    og = _extract_og_tags(soup)
    assert og["title"] == "OG Title"
    assert og["description"] == "OG Description"
    assert og["image"] == "https://example.com/img.png"
    assert og["type"] == "article"


def test_extract_og_tags_fallback_to_meta_description():
    """When og:description is missing, falls back to <meta name='description'>."""
    soup = BeautifulSoup(HTML_WITH_META_DESC, "html.parser")
    og = _extract_og_tags(soup)
    assert og["title"] is None  # no og:title in this HTML
    assert og["description"] == "Meta fallback description"


def test_extract_og_tags_empty_page():
    """Empty page returns all None values."""
    soup = BeautifulSoup(b"<html></html>", "html.parser")
    og = _extract_og_tags(soup)
    assert og["title"] is None
    assert og["description"] is None
    assert og["image"] is None
    assert og["type"] is None


# ---------------------------------------------------------------------------
# _fetch_page — successful fetch
# ---------------------------------------------------------------------------


def test_fetch_page_successful_extracts_all_metadata():
    """Mocked 200 HEAD + 200 GET with full HTML → all metadata fields populated."""
    head_mock = _make_head_mock(200)
    get_mock = _make_get_mock(200, MINIMAL_HTML)

    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock, get_mock]):
        result = _fetch_page("https://example.com")

    assert result["status"] == 200
    assert result["is_dead"] is False
    assert result["is_soft_dead"] is False
    assert result["title"] == "Page Title"
    assert result["og_title"] == "OG Title"
    assert result["og_description"] == "OG Description"
    assert result["og_image"] == "https://example.com/img.png"
    assert result["og_type"] == "article"
    assert result["canonical_url"] == "https://example.com/canonical"
    assert result["error"] is None


def test_fetch_page_successful_no_canonical_falls_back_to_url():
    """When no <link rel='canonical'> exists, canonical_url is the input URL."""
    html_no_canonical = b"<html><head><title>T</title></head><body></body></html>"
    head_mock = _make_head_mock(200)
    get_mock = _make_get_mock(200, html_no_canonical)

    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock, get_mock]):
        result = _fetch_page("https://example.com/page")

    assert result["canonical_url"] == "https://example.com/page"


# ---------------------------------------------------------------------------
# _fetch_page — dead links
# ---------------------------------------------------------------------------


def test_fetch_page_dead_404_returns_early():
    """HEAD returns 404 → is_dead=True, returns immediately without GET."""
    http_err = _make_http_error(404)

    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=http_err):
        result = _fetch_page("https://example.com/dead")

    assert result["status"] == 404
    assert result["is_dead"] is True
    assert result["is_soft_dead"] is False
    # No GET was attempted, so these remain None
    assert result["title"] is None
    assert result["og_title"] is None


def test_fetch_page_dead_500_returns_early():
    """HEAD returns 500 → is_dead=True, returns immediately without GET."""
    http_err = _make_http_error(500)

    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=http_err):
        result = _fetch_page("https://example.com/dead")

    assert result["status"] == 500
    assert result["is_dead"] is True
    assert result["is_soft_dead"] is False


# ---------------------------------------------------------------------------
# _fetch_page — soft-dead
# ---------------------------------------------------------------------------


def test_fetch_page_soft_dead_403():
    """HEAD returns 403 → is_soft_dead=True, GET also 403 → returns with status."""
    http_err = _make_http_error(403)

    # Two calls: HEAD then GET, both raise HTTPError(403)
    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[http_err, http_err]):
        result = _fetch_page("https://example.com/forbidden")

    assert result["status"] == 403
    assert result["is_dead"] is False  # 403 is soft-dead, not dead
    assert result["is_soft_dead"] is True


# ---------------------------------------------------------------------------
# _fetch_page — non-HTML content
# ---------------------------------------------------------------------------


def test_fetch_page_non_html_content_returns_early():
    """HEAD returns 200 with application/json → is_dead=False, returns without GET."""
    head_mock = _make_head_mock(200, content_type="application/json")

    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock]):
        result = _fetch_page("https://example.com/api")

    assert result["status"] == 200
    assert result["is_dead"] is False
    assert result["is_soft_dead"] is False
    # No GET was attempted
    assert result["title"] is None
