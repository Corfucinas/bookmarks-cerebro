"""Shared utilities for Bookmarks Cerebro."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import orjson

# Logging setup
logger = logging.getLogger("cerebro")


def setup_logging(level: int = logging.INFO) -> None:
    """Configure rich console logging."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def slugify(text: str, max_length: int = 80) -> str:
    """Create URL-safe slug from arbitrary text."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text)
    return text[:max_length].rstrip("-")


def safe_filename(text: str, max_length: int = 100) -> str:
    """Create filesystem-safe filename."""
    text = re.sub(r"[^\w\s.-]", "", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = text[:max_length].rstrip(".")
    if not text or set(text) == {"-"}:
        return "untitled"
    return text


def epoch_to_iso(epoch_str: str | int | None) -> str | None:
    """Convert Netscape ADD_DATE Unix epoch to ISO 8601."""
    if not epoch_str:
        return None
    try:
        epoch = int(epoch_str)
        if epoch == 0:
            return None
        dt = datetime.fromtimestamp(epoch, tz=timezone.utc)
        return dt.isoformat()
    except (ValueError, OSError, OverflowError):
        return None


def compute_id(url: str, title: str) -> str:
    """Deterministic bookmark ID from URL + title.

    Uses a length-prefixed encoding so that url and title cannot collide
    via the ``::`` separator (``url='a::b', title='c'`` vs ``url='a', title='b::c'``).
    """
    payload = f"{len(url)}:{url}::{len(title)}:{title}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_json(path: Path) -> Any:
    """Fast JSON load with orjson."""
    with open(path, "rb") as f:
        return orjson.loads(f.read())


def save_json(path: Path, data: Any, pretty: bool = True) -> None:
    """Fast JSON save with orjson."""
    option = orjson.OPT_INDENT_2 if pretty else 0
    with open(path, "wb") as f:
        f.write(orjson.dumps(data, option=option))


def ensure_dir(path: Path) -> Path:
    """Create directory if missing and return path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_repo_root() -> Path:
    """Return repository root (cwd or git root)."""
    cwd = Path.cwd()
    if (cwd / ".git").exists():
        return cwd
    # Try to find git root upward
    for parent in cwd.parents:
        if (parent / ".git").exists():
            return parent
    return cwd


def extract_domain(url: str) -> str:
    """Extract domain (netloc) from URL."""
    from urllib.parse import urlparse

    try:
        parsed = urlparse(url)
        return re.sub(r"^www\.", "", parsed.netloc.lower())
    except Exception:
        return ""


_MULTIPART_TLD_SUFFIXES: frozenset[str] = frozenset(
    {
        "co.uk",
        "com.au",
        "co.jp",
        "co.nz",
        "com.br",
        "co.in",
        "com.mx",
        "co.kr",
        "com.cn",
        "org.uk",
        "ac.uk",
        "gov.uk",
        "co.za",
        "com.sg",
        "co.id",
        "com.hk",
        "com.tw",
        "co.th",
        "com.my",
        "co.il",
        "com.ar",
        "com.co",
        "co.pe",
        "com.ng",
        "co.ke",
        "com.eg",
        "com.pk",
        "com.bd",
        "com.tr",
        "com.vn",
        "co.ph",
        "com.sa",
        "net.au",
        "org.au",
        "edu.au",
        "co.hu",
        "co.at",
        "co.no",
        "co.se",
        "co.dk",
        "co.fi",
        "co.pl",
        "co.gr",
        "co.pt",
        "co.it",
        "co.es",
        "co.fr",
        "co.de",
        "co.nl",
        "co.be",
        "co.ch",
        "co.cz",
        "co.sk",
        "co.ro",
        "co.bg",
        "co.hr",
        "co.rs",
        "co.si",
        "co.lt",
        "co.lv",
        "co.ee",
        "co.ie",
    }
)


def extract_tld_plus_one(url: str) -> str:
    """Extract registered domain (e.g. github.com).

    Handles multi-part TLD suffixes such as ``co.uk`` and ``com.au`` so that
    ``www.google.co.uk`` returns ``google.co.uk`` rather than ``co.uk``.
    """
    domain = extract_domain(url)
    parts = domain.split(".")
    if len(parts) >= 3:
        candidate_suffix = ".".join(parts[-2:])
        if candidate_suffix in _MULTIPART_TLD_SUFFIXES:
            return ".".join(parts[-3:])
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return domain
