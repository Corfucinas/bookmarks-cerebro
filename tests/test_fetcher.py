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


# ---------------------------------------------------------------------------
# Additional coverage: _is_dead / _is_soft_dead / SSL / _read_body
# ---------------------------------------------------------------------------
def test_is_dead_various_statuses():
    """Verify _is_dead across boundary statuses."""
    assert _is_dead(404) is True
    assert _is_dead(410) is True
    assert _is_dead(500) is True
    assert _is_dead(200) is False
    assert _is_dead(None) is True
    assert _is_dead(301) is False


def test_is_soft_dead_various_statuses():
    """Verify _is_soft_dead across boundary statuses."""
    assert _is_soft_dead(401) is True
    assert _is_soft_dead(403) is True
    assert _is_soft_dead(429) is True
    assert _is_soft_dead(200) is False
    assert _is_soft_dead(None) is False


def test_create_ssl_context_is_permissive():
    """_create_ssl_context disables hostname check and cert verification."""
    import ssl

    from cerebro.fetcher import _create_ssl_context

    actual = _create_ssl_context()
    assert isinstance(actual, ssl.SSLContext)
    assert actual.check_hostname is False
    assert actual.verify_mode == ssl.CERT_NONE


def test_read_body_empty_returns_empty_string():
    """_read_body returns '' when response body is empty."""
    from cerebro.fetcher import _read_body

    resp = MagicMock()
    resp.read.return_value = b""
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    assert _read_body(resp) == ""


def test_read_body_with_charset_extracts_encoding():
    """_read_body parses charset from Content-Type and decodes accordingly."""
    from cerebro.fetcher import _read_body

    resp = MagicMock()
    resp.read.return_value = "héllo".encode("latin-1")
    resp.headers = {"Content-Type": "text/html; charset=latin-1"}
    body = _read_body(resp)
    assert body == "héllo"


def test_read_body_decode_error_returns_empty():
    """_read_body returns '' when decode raises ValueError (caught by except)."""
    from cerebro.fetcher import _read_body

    class BadBytes(bytes):
        def decode(self, encoding: str = ..., errors: str = ...) -> str:
            raise ValueError("simulated")

    resp = MagicMock()
    resp.read.return_value = BadBytes(b"")
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    assert _read_body(resp) == ""


def test_fetch_page_head_retry_then_success():
    """HEAD returns None twice then succeeds — retry loop is exercised."""
    head_ok = _make_head_mock(200, content_type="application/pdf")
    with (
        patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[None, None, head_ok]),
        patch("cerebro.fetcher.time.sleep"),
    ):
        result = _fetch_page("https://example.com/retry")
    assert result["status"] == 200
    assert result["is_dead"] is False


def test_fetch_page_get_retry_then_success():
    """HEAD soft-dead 403; first GET None, second HTTPError(403) -> status set."""
    http_err = _make_http_error(403)
    # HEAD raises HTTPError(403) -> returned (not None), HEAD loop breaks.
    # GET: first None (URLError), second raises HTTPError(403).
    with (
        patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[http_err, None, http_err]),
        patch("cerebro.fetcher.time.sleep"),
    ):
        result = _fetch_page("https://example.com/forbidden-retry")
    assert result["status"] == 403
    assert result["is_soft_dead"] is True


def test_fetch_page_get_non_html_returns_early():
    """200 HEAD + 200 GET with application/pdf — returns without parsing body."""
    head_mock = _make_head_mock(200)
    get_mock = _make_get_mock(200, b"%PDF-1.4", content_type="application/pdf")
    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock, get_mock]):
        result = _fetch_page("https://example.com/doc.pdf")
    assert result["status"] == 200
    assert result["is_dead"] is False
    assert result["title"] is None


def test_fetch_page_empty_body_sets_error():
    """200 GET with empty body -> result['error'] == 'Empty body'."""
    head_mock = _make_head_mock(200)
    get_mock = _make_get_mock(200, b"")
    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock, get_mock]):
        result = _fetch_page("https://example.com/empty")
    assert result["status"] == 200
    assert result["is_dead"] is False
    assert result["error"] == "Empty body"


def test_fetch_page_all_get_attempts_failed():
    """HEAD soft-dead 403 + GET always None -> error 'All GET attempts failed'."""
    http_err = _make_http_error(403)
    with (
        patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[http_err, None, None]),
        patch("cerebro.fetcher.time.sleep"),
    ):
        result = _fetch_page("https://example.com/always-fail")
    assert result["status"] == 403
    assert result["is_soft_dead"] is True
    assert result["error"] == "All GET attempts failed"


def test_fetch_page_attribute_error_status_zero():
    """Response without getcode() -> status defaults to 0."""
    head_mock = MagicMock()
    head_mock.getcode.side_effect = AttributeError("no getcode")
    head_mock.headers = {"Content-Type": "text/html"}
    get_mock = MagicMock()
    get_mock.getcode.side_effect = AttributeError("no getcode")
    get_mock.headers = {"Content-Type": "text/html"}
    get_mock.read.return_value = MINIMAL_HTML
    with patch("cerebro.fetcher.urllib.request.urlopen", side_effect=[head_mock, get_mock]):
        result = _fetch_page("https://example.com/no-getcode")
    assert result["status"] == 0
    assert result["is_dead"] is False


# ---------------------------------------------------------------------------
# fetch_bookmarks — integration with mocked _fetch_page
# ---------------------------------------------------------------------------
def test_fetch_bookmarks_empty_input_returns_empty():
    """Empty bookmark list -> returns empty list without spawning workers."""
    from cerebro.fetcher import fetch_bookmarks

    assert fetch_bookmarks([]) == []


def test_fetch_bookmarks_marks_dead():
    """Dead _fetch_page result sets is_dead_link=True on the bookmark."""
    from cerebro.fetcher import fetch_bookmarks
    from cerebro.models import Bookmark

    bm = Bookmark(id="dead-1", title="Dead", url="https://example.com/dead")
    dead_result = {"status": 404, "is_dead": True, "is_soft_dead": False}
    with patch("cerebro.fetcher._fetch_page", return_value=dead_result):
        result = fetch_bookmarks([bm], max_workers=1)
    assert len(result) == 1
    assert result[0].is_dead_link is True
    assert result[0].http_status == 404
    assert result[0].fetched_metadata == dead_result


def test_fetch_bookmarks_marks_alive_and_soft_dead():
    """Mix of alive, dead, soft-dead bookmarks; metadata set correctly."""
    from cerebro.fetcher import fetch_bookmarks
    from cerebro.models import Bookmark

    alive = Bookmark(id="a1", title="Alive", url="https://example.com/alive")
    soft = Bookmark(id="s1", title="Soft", url="https://example.com/soft")
    dead = Bookmark(id="d1", title="Dead", url="https://example.com/dead")

    results = {
        "https://example.com/alive": {"status": 200, "is_dead": False, "is_soft_dead": False},
        "https://example.com/soft": {"status": 403, "is_dead": False, "is_soft_dead": True},
        "https://example.com/dead": {"status": 404, "is_dead": True, "is_soft_dead": False},
    }

    def fake_fetch(url, timeout):
        return results[url]

    with patch("cerebro.fetcher._fetch_page", side_effect=fake_fetch):
        out = fetch_bookmarks([alive, soft, dead], max_workers=1)

    by_id = {b.id: b for b in out}
    assert by_id["a1"].is_dead_link is False
    assert by_id["s1"].is_dead_link is False
    assert by_id["d1"].is_dead_link is True
    assert by_id["s1"].http_status == 403


def test_fetch_bookmarks_exception_marks_dead():
    """Exception from _fetch_page future -> bookmark marked dead with error metadata."""
    from cerebro.fetcher import fetch_bookmarks
    from cerebro.models import Bookmark

    bm = Bookmark(id="err-1", title="Err", url="https://example.com/err")
    with patch("cerebro.fetcher._fetch_page", side_effect=RuntimeError("boom")):
        out = fetch_bookmarks([bm], max_workers=1, timeout=1)
    assert out[0].is_dead_link is True
    assert out[0].fetched_metadata["error"] == "boom"
