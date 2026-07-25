"""Tests for cerebro.utils."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cerebro.utils import (
    compute_id,
    ensure_dir,
    epoch_to_iso,
    extract_domain,
    extract_tld_plus_one,
    get_repo_root,
    load_json,
    safe_filename,
    save_json,
    slugify,
)

# ---------------------------------------------------------------------------
# compute_id — collision resistance
# ---------------------------------------------------------------------------


def test_compute_id_no_collision():
    """Length-prefixed encoding must distinguish url::title splits that share a delimiter."""
    # url="a::b", title="c" vs url="a", title="b::c" — naive f"{url}::{title}" collides
    assert compute_id("a::b", "c") != compute_id("a", "b::c")


def test_compute_id_deterministic():
    """Same inputs produce the same id."""
    assert compute_id("https://example.com", "Hello") == compute_id("https://example.com", "Hello")


def test_compute_id_different_urls_differ():
    """Different urls produce different ids."""
    assert compute_id("https://a.com", "Title") != compute_id("https://b.com", "Title")


def test_compute_id_different_titles_differ():
    """Different titles produce different ids."""
    assert compute_id("https://a.com", "Title A") != compute_id("https://a.com", "Title B")


# ---------------------------------------------------------------------------
# extract_tld_plus_one — multi-part TLDs
# ---------------------------------------------------------------------------


def test_extract_tld_plus_one_multipart():
    """Known multi-part TLD suffixes yield 3-part registered domains."""
    assert extract_tld_plus_one("https://www.google.co.uk") == "google.co.uk"
    assert extract_tld_plus_one("https://www.amazon.com.au") == "amazon.com.au"
    assert extract_tld_plus_one("https://example.co.jp") == "example.co.jp"


def test_extract_tld_plus_one_simple():
    """Standard two-part TLDs still return two parts."""
    assert extract_tld_plus_one("https://github.com") == "github.com"
    assert extract_tld_plus_one("https://example.org") == "example.org"


def test_extract_tld_plus_one_subdomain():
    """Subdomains are stripped, registered domain returned."""
    assert extract_tld_plus_one("https://blog.example.co.uk") == "example.co.uk"


# ---------------------------------------------------------------------------
# safe_filename — empty/dash-only results
# ---------------------------------------------------------------------------


def test_safe_filename_empty_result():
    """Dots-only, dash-only, and whitespace-only inputs must not produce empty filenames."""
    assert safe_filename("...") == "untitled"
    assert safe_filename("---") == "untitled"
    assert safe_filename("   ") == "untitled"


def test_safe_filename_normal_input():
    """Normal input still produces a non-empty filename."""
    assert safe_filename("normal title") != ""
    assert safe_filename("normal title") == "normal-title"


def test_safe_filename_strip_punctuation():
    """Trailing dots are stripped but result remains non-empty."""
    assert safe_filename("title...") == "title"


# ---------------------------------------------------------------------------
# slugify
# ---------------------------------------------------------------------------


def test_slugify_basic():
    """Lowercase and replace spaces with hyphens."""
    assert slugify("Hello World!") == "hello-world"


def test_slugify_max_length():
    """Output is truncated to max_length."""
    text = "a" * 100
    assert len(slugify(text, max_length=20)) == 20


def test_slugify_special_chars():
    """Non-word characters are stripped."""
    assert slugify("C++ Tutorial!") == "c-tutorial"


# ---------------------------------------------------------------------------
# epoch_to_iso
# ---------------------------------------------------------------------------


def test_epoch_to_iso_valid():
    """A real epoch seconds value returns an ISO 8601 UTC string."""
    assert epoch_to_iso("1609459200") == "2021-01-01T00:00:00+00:00"


def test_epoch_to_iso_zero():
    """Epoch 0 is treated as missing and returns None."""
    assert epoch_to_iso("0") is None


def test_epoch_to_iso_none():
    """None input returns None."""
    assert epoch_to_iso(None) is None


def test_epoch_to_iso_invalid():
    """Non-numeric input returns None."""
    assert epoch_to_iso("abc") is None


# ---------------------------------------------------------------------------
# load_json / save_json
# ---------------------------------------------------------------------------


def test_load_json_round_trip(tmp_path: Path):
    """save_json then load_json preserves data."""
    p = tmp_path / "data.json"
    payload = {"a": 1, "b": [2, 3], "c": {"d": "x"}}
    save_json(p, payload)
    assert load_json(p) == payload


def test_save_json_creates_file(tmp_path: Path):
    """save_json writes a file with valid JSON content."""
    p = tmp_path / "out.json"
    save_json(p, {"hello": "world"})
    assert p.exists()
    import json

    assert json.loads(p.read_text()) == {"hello": "world"}


# ---------------------------------------------------------------------------
# ensure_dir
# ---------------------------------------------------------------------------


def test_ensure_dir_creates_missing(tmp_path: Path):
    """ensure_dir creates nested directories and returns the path."""
    nested = tmp_path / "a" / "b" / "c"
    result = ensure_dir(nested)
    assert result == nested
    assert nested.exists() and nested.is_dir()


# ---------------------------------------------------------------------------
# get_repo_root
# ---------------------------------------------------------------------------


def test_get_repo_root():
    """From the repo root, returns a Path containing .git."""
    root = get_repo_root()
    assert (root / ".git").exists()


# ---------------------------------------------------------------------------
# extract_domain
# ---------------------------------------------------------------------------


def test_extract_domain_basic():
    """Extracts netloc and strips leading www."""
    assert extract_domain("https://www.example.com/path") == "example.com"


def test_extract_domain_no_protocol():
    """Handles URLs without an explicit protocol."""
    assert extract_domain("//example.com/path") == "example.com"


def test_extract_domain_invalid():
    """Invalid URLs return an empty string."""
    assert extract_domain("not a url") == ""
