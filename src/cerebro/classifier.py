"""Hybrid bookmark classifier: domain heuristics + keyword matching + ML fallback."""

from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import KNeighborsClassifier

from .models import Bookmark
from .taxonomy import TaxonomyNode, load_taxonomy
from .utils import extract_tld_plus_one

logger = logging.getLogger("cerebro")

# Domain → category mapping (high confidence)
DOMAIN_RULES: dict[str, list[str]] = {
    "github.com": ["Programming", "DevEx"],
    "stackoverflow.com": ["Programming", "Reference"],
    "gitlab.com": ["Programming", "DevEx"],
    "arxiv.org": ["Research", "Papers"],
    "paperswithcode.com": ["AI/ML", "Research"],
    "huggingface.co": ["AI/ML", "Tools"],
    "pytorch.org": ["AI/ML", "Frameworks"],
    "tensorflow.org": ["AI/ML", "Frameworks"],
    "kaggle.com": ["AI/ML", "Tools"],
    "figma.com": ["Design", "Tools"],
    "dribbble.com": ["Design", "UI/UX"],
    "awwwards.com": ["Design", "UI/UX"],
    "aws.amazon.com": ["Systems", "Cloud"],
    "cloud.google.com": ["Systems", "Cloud"],
    "azure.microsoft.com": ["Systems", "Cloud"],
    "docker.com": ["Systems", "Containers"],
    "kubernetes.io": ["Systems", "Containers"],
    "torproject.org": ["Systems", "Networking"],
    "medium.com": ["Research", "Courses"],
    "dev.to": ["Programming", "Patterns"],
    "freecodecamp.org": ["Research", "Courses"],
    "coursera.org": ["Research", "Courses"],
    "udemy.com": ["Research", "Courses"],
    "youtube.com": ["Research", "Courses"],
    "twitter.com": ["Life", "Personal"],
    "x.com": ["Life", "Personal"],
    "reddit.com": ["Life", "Personal"],
    "linkedin.com": ["Career", "Skills"],
    "indeed.com": ["Career", "Interview"],
    "glassdoor.com": ["Career", "Interview"],
    "coinbase.com": ["Finance", "Crypto"],
    "binance.com": ["Finance", "Crypto"],
    "etherscan.io": ["Finance", "Crypto"],
    "coingecko.com": ["Finance", "Crypto"],
    "tradingview.com": ["Finance", "Quant"],
    "investopedia.com": ["Finance", "Markets"],
    "wikipedia.org": ["Reference", "Wikipedia"],
    "w3schools.com": ["Reference", "Cheatsheets"],
    "mdn.mozilla.org": ["Reference", "Cheatsheets"],
    "caniuse.com": ["Design", "Frontend"],
    "npmjs.com": ["Programming", "Frameworks"],
    "pypi.org": ["Programming", "Languages"],
    "crates.io": ["Programming", "Languages"],
    "news.ycombinator.com": ["Programming", "Patterns"],
    "producthunt.com": ["Career", "Business"],
    "angel.co": ["Career", "Business"],
    "kickstarter.com": ["Career", "Business"],
    "arduino.cc": ["Hardware", "Microcontrollers"],
    "raspberrypi.org": ["Hardware", "Microcontrollers"],
    "adafruit.com": ["Hardware", "Electronics"],
    "sparkfun.com": ["Hardware", "Electronics"],
    "expedia.com": ["Life", "Travel"],
    "booking.com": ["Life", "Travel"],
    "tripadvisor.com": ["Life", "Travel"],
    "allrecipes.com": ["Life", "Food"],
    "foodnetwork.com": ["Life", "Food"],
    "myfitnesspal.com": ["Life", "Health"],
    "strava.com": ["Life", "Health"],
    "spotify.com": ["Life", "Hobbies"],
    "soundcloud.com": ["Life", "Hobbies"],
    "ultimate-guitar.com": ["Life", "Hobbies"],
    "obsidian.md": ["Productivity", "Workflows"],
    "notion.so": ["Productivity", "Workflows"],
    "trello.com": ["Productivity", "Workflows"],
    "proton.me": ["Systems", "Security"],
    "eff.org": ["Systems", "Security"],
    "nmap.org": ["Systems", "Security"],
    "grafana.com": ["Systems", "Observability"],
    "prometheus.io": ["Systems", "Observability"],
    "datadoghq.com": ["Systems", "Observability"],
    "linuxize.com": ["Systems", "Linux"],
    "archlinux.org": ["Systems", "Linux"],
    "gentoo.org": ["Systems", "Linux"],
    "debian.org": ["Systems", "Linux"],
}

# Keyword → category mapping
KEYWORD_RULES: list[tuple[list[str], list[str], float]] = [
    (
        [
            "machine learning",
            "deep learning",
            "neural network",
            "transformer",
            "llm",
            "gpt",
            "diffusion",
            "pytorch",
            "tensorflow",
            "jax",
            "huggingface",
            "model",
            "training",
            "inference",
            "embedding",
            "vector",
            "rag",
            "fine-tune",
        ],
        ["AI/ML", "Models"],
        0.85,
    ),
    (
        [
            "quantitative",
            "backtest",
            "algorithmic trading",
            "trading strategy",
            "portfolio",
            "risk management",
            "sharpe",
            "alpha",
            "beta",
        ],
        ["Finance", "Quant"],
        0.90,
    ),
    (
        [
            "blockchain",
            "ethereum",
            "solidity",
            "smart contract",
            "defi",
            "nft",
            "bitcoin",
            "crypto",
            "token",
            "flash loan",
            "dex",
        ],
        ["Finance", "Crypto"],
        0.90,
    ),
    (
        ["docker", "kubernetes", "k8s", "container", "helm", "pod", "microservice"],
        ["Systems", "Containers"],
        0.85,
    ),
    (
        ["aws", "gcp", "azure", "serverless", "lambda", "cloud", "s3", "ec2"],
        ["Systems", "Cloud"],
        0.85,
    ),
    (
        ["linux", "ubuntu", "debian", "arch", "gentoo", "kernel", "systemd", "bash"],
        ["Systems", "Linux"],
        0.85,
    ),
    (
        [
            "security",
            "cryptography",
            "encryption",
            "cipher",
            "hash",
            "rsa",
            "aes",
            "tor",
            "vpn",
            "pentest",
            "cve",
        ],
        ["Systems", "Security"],
        0.85,
    ),
    (
        [
            "css",
            "html",
            "javascript",
            "react",
            "vue",
            "frontend",
            "ui",
            "ux",
            "responsive",
            "tailwind",
            "bootstrap",
        ],
        ["Design", "Frontend"],
        0.80,
    ),
    (
        ["figma", "sketch", "adobe", "photoshop", "illustrator", "design system"],
        ["Design", "Tools"],
        0.85,
    ),
    (
        ["python", "django", "fastapi", "flask", "pandas", "numpy", "scipy", "pytest"],
        ["Programming", "Languages"],
        0.80,
    ),
    (["rust", "cargo", "tokio", "actix"], ["Programming", "Languages"], 0.85),
    (["golang", "go lang"], ["Programming", "Languages"], 0.85),
    (["typescript", "node.js", "nodejs", "express", "nestjs"], ["Programming", "Languages"], 0.80),
    (["java", "spring", "jvm"], ["Programming", "Languages"], 0.80),
    (
        ["sql", "database", "postgres", "mysql", "sqlite", "orm", "query"],
        ["Programming", "Data"],
        0.80,
    ),
    (["devops", "ci/cd", "jenkins", "github actions", "gitlab ci"], ["Programming", "DevEx"], 0.80),
    (["test", "testing", "pytest", "unittest", "mock", "tdd"], ["Programming", "Testing"], 0.75),
    (
        ["monitoring", "logging", "tracing", "prometheus", "grafana", "jaeger"],
        ["Systems", "Observability"],
        0.80,
    ),
    (
        ["interview", "leetcode", "system design", "coding interview", "behavioral"],
        ["Career", "Interview"],
        0.85,
    ),
    (["freelance", "upwork", "fiverr", "contract", "client"], ["Career", "Freelancing"], 0.80),
    (
        ["startup", "business", "marketing", "seo", "growth", "product"],
        ["Career", "Business"],
        0.75,
    ),
    (
        ["arduino", "raspberry pi", "esp32", " microcontroller", "iot", "sensor"],
        ["Hardware", "Microcontrollers"],
        0.85,
    ),
    (
        ["obsidian", "notion", "zettelkasten", "pkm", "note-taking", "workflow"],
        ["Productivity", "Workflows"],
        0.80,
    ),
    (
        ["self-host", "homelab", "nas", "server", "pi-hole", "nextcloud"],
        ["Productivity", "Self-Hosting"],
        0.85,
    ),
    (["guitar", "music", "chord", "tab", "song"], ["Life", "Hobbies"], 0.80),
    (["travel", "destination", "hotel", "flight", "trip", "vacation"], ["Life", "Travel"], 0.80),
    (["recipe", "cooking", "food", "restaurant", "cuisine"], ["Life", "Food"], 0.80),
    (["fitness", "workout", "gym", "nutrition", "health", "diet"], ["Life", "Health"], 0.80),
    (
        ["paper", "arxiv", "research", "journal", "academic", "scientific", "publication"],
        ["Research", "Papers"],
        0.85,
    ),
    (
        ["course", "tutorial", "learn", "mooc", "class", "lesson", "bootcamp"],
        ["Research", "Courses"],
        0.75,
    ),
    (["book", "novel", "literature", "reading", "author"], ["Research", "Books"], 0.75),
    (
        ["cheatsheet", "reference", "docs", "documentation", "manual", "guide"],
        ["Reference", "Cheatsheets"],
        0.75,
    ),
    (["wikipedia", "encyclopedia", "wiki"], ["Reference", "Wikipedia"], 0.90),
    (["osint", "intelligence", "reconnaissance", "investigation"], ["Reference", "OSINT"], 0.85),
    (
        ["network", "protocol", "tcp/ip", "http", "dns", "firewall", "router"],
        ["Systems", "Networking"],
        0.80,
    ),
]


class BookmarkClassifier:
    """Classify bookmarks into taxonomy using hybrid approach."""

    def __init__(self, taxonomy_path: Path | str) -> None:
        self.taxonomy = load_taxonomy(taxonomy_path)
        self.leaves = self.taxonomy.all_leaves()
        self.leaf_names = ["/".join(leaf.breadcrumb[1:]) for leaf in self.leaves]
        self.ml_classifier: KNeighborsClassifier | None = None
        self.vectorizer: TfidfVectorizer | None = None
        self._ml_ready = False

    def classify(self, bookmark: Bookmark) -> tuple[list[str], float]:
        """Return (breadcrumbs, confidence_score)."""
        domain = extract_tld_plus_one(bookmark.url)
        if domain in DOMAIN_RULES:
            breadcrumbs = DOMAIN_RULES[domain]
            return breadcrumbs, 0.90

        text = f"{bookmark.title} {bookmark.url}".lower()
        for keywords, breadcrumbs, confidence in KEYWORD_RULES:
            if any(kw in text for kw in keywords):
                return breadcrumbs, confidence

        if self._ml_ready:
            return self._ml_classify(text)

        if bookmark.raw_folder_path:
            mapped = self._map_raw_folder(bookmark.raw_folder_path)
            if mapped:
                return mapped, 0.50

        return ["Reference", "Utilities"], 0.30

    def _map_raw_folder(self, raw_path: str) -> list[str] | None:
        """Map old folder paths to new taxonomy."""
        raw_lower = raw_path.lower()
        mappings = {
            "coding/python": ["Programming", "Languages"],
            "coding/rust": ["Programming", "Languages"],
            "coding/java": ["Programming", "Languages"],
            "coding/javascript": ["Programming", "Languages"],
            "coding/typescript": ["Programming", "Languages"],
            "coding/sql": ["Programming", "Data"],
            "coding/yaml": ["Programming", "DevEx"],
            "coding/frontend": ["Design", "Frontend"],
            "coding/mobile": ["Programming", "Frameworks"],
            "coding/dev tools": ["Programming", "DevEx"],
            "coding/github": ["Programming", "DevEx"],
            "coding/linux": ["Systems", "Linux"],
            "coding/linux/security": ["Systems", "Security"],
            "coding/cryptography": ["Systems", "Security"],
            "coding/best practices": ["Programming", "Patterns"],
            "coding/machine learning": ["AI/ML", "Frameworks"],
            "quantitative trading": ["Finance", "Quant"],
            "cryptocurrency": ["Finance", "Crypto"],
            "hacking": ["Systems", "Security"],
            "steganography": ["Systems", "Security"],
            "osint": ["Reference", "OSINT"],
            "guitar": ["Life", "Hobbies"],
            "study": ["Research", "Courses"],
            "personal": ["Life", "Personal"],
            "travel": ["Life", "Travel"],
            "games": ["Life", "Hobbies"],
            "bodybuilding": ["Life", "Health"],
            "plants": ["Life", "Hobbies"],
            "docker": ["Systems", "Containers"],
            "kubernetes": ["Systems", "Containers"],
            "microservices": ["Systems", "Containers"],
            "nginx": ["Systems", "Networking"],
            "cloud architecture": ["Systems", "Cloud"],
            "api": ["Programming", "Patterns"],
            "http": ["Systems", "Networking"],
            "asyncio": ["Programming", "Patterns"],
            "webscrapping": ["Programming", "DevEx"],
            "interview": ["Career", "Interview"],
            "barclays": ["Finance", "Markets"],
            "banking": ["Finance", "Markets"],
            "consultant": ["Career", "Business"],
            "freelancing": ["Career", "Freelancing"],
            "gentoo": ["Systems", "Linux"],
            "arch": ["Systems", "Linux"],
            "vim": ["Productivity", "Tools"],
            "tmux": ["Productivity", "Tools"],
            "vscode": ["Programming", "DevEx"],
            "monitoring": ["Systems", "Observability"],
            "tracing": ["Systems", "Observability"],
            "analytics": ["Systems", "Observability"],
            "indicators": ["Finance", "Quant"],
            "strategies": ["Finance", "Quant"],
            "flash loans eth": ["Finance", "Crypto"],
            "dex": ["Finance", "Crypto"],
            "solidity": ["Finance", "Crypto"],
            "arduino": ["Hardware", "Microcontrollers"],
            "microcontroller": ["Hardware", "Microcontrollers"],
            "opencv": ["AI/ML", "Tools"],
            "react": ["Design", "Frontend"],
            "wikipedia": ["Reference", "Wikipedia"],
            "documentation": ["Reference", "Cheatsheets"],
            "obsidian": ["Productivity", "Workflows"],
            "fastapi": ["Programming", "Frameworks"],
            "django": ["Programming", "Frameworks"],
            "pandas": ["Programming", "Data"],
            "cython": ["Programming", "Languages"],
            "pysqlite": ["Programming", "Data"],
            "regexp": ["Programming", "Patterns"],
            "linting": ["Programming", "DevEx"],
            "pytest": ["Programming", "Testing"],
            "openai": ["AI/ML", "Tools"],
            "langchain": ["AI/ML", "Tools"],
            "chemistry": ["Research", "Papers"],
            "mathematics": ["Research", "Papers"],
            "stadistics": ["Research", "Papers"],
            "harvard": ["Research", "Courses"],
            "oxford": ["Research", "Courses"],
            "memorization": ["Research", "Courses"],
            "viewfin": ["Finance", "Markets"],
            "raspberry pi": ["Hardware", "Microcontrollers"],
            "betterment": ["Finance", "Markets"],
            "absolute array": ["Reference", "Utilities"],
            "other": ["Reference", "Utilities"],
        }
        for pattern, breadcrumbs in mappings.items():
            if pattern in raw_lower:
                return breadcrumbs
        return None

    def _ml_classify(self, text: str) -> tuple[list[str], float]:
        if not self.ml_classifier or not self.vectorizer:
            return ["Reference", "Utilities"], 0.20
        try:
            X = self.vectorizer.transform([text])
            proba = self.ml_classifier.predict_proba(X)[0]
            pred_idx = np.argmax(proba)
            confidence = float(proba[pred_idx])
            leaf = self.leaves[pred_idx]
            return leaf.breadcrumb[1:], confidence
        except Exception as e:
            logger.warning(f"ML classification failed: {e}")
            return ["Reference", "Utilities"], 0.20

    def train_ml(self, bookmarks: list[Bookmark]) -> None:
        """Train ML fallback on already-classified bookmarks."""
        classified = []
        labels = []
        for bm in bookmarks:
            cat, conf = self.classify(bm)
            if conf >= 0.70:
                text = f"{bm.title} {bm.url}"
                classified.append(text)
                leaf_name = "/".join(cat)
                try:
                    idx = self.leaf_names.index(leaf_name)
                    labels.append(idx)
                except ValueError:
                    pass

        if len(classified) < 100:
            logger.warning(f"Not enough training data: {len(classified)} samples")
            return

        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            ngram_range=(1, 2),
            min_df=2,
            stop_words="english",
        )
        X = self.vectorizer.fit_transform(classified)
        self.ml_classifier = KNeighborsClassifier(n_neighbors=5, weights="distance")
        self.ml_classifier.fit(X, labels)
        self._ml_ready = True
        logger.info(f"ML classifier trained on {len(classified)} samples")


def classify_bookmarks(
    bookmarks: list[Bookmark],
    taxonomy_path: Path | str,
    train_ml: bool = True,
) -> list[Bookmark]:
    """Classify all bookmarks and return enriched list."""
    classifier = BookmarkClassifier(taxonomy_path)

    logger.info("Running heuristic classification...")
    for bm in bookmarks:
        breadcrumbs, confidence = classifier.classify(bm)
        bm.category_breadcrumbs = breadcrumbs
        bm.confidence_score = confidence

    if train_ml:
        logger.info("Training ML fallback...")
        classifier.train_ml(bookmarks)
        for bm in bookmarks:
            if bm.confidence_score < 0.60:
                breadcrumbs, confidence = classifier.classify(bm)
                bm.category_breadcrumbs = breadcrumbs
                bm.confidence_score = confidence

    histogram = Counter(bm.category_path for bm in bookmarks)
    logger.info("Category distribution:")
    for path, count in histogram.most_common(15):
        logger.info(f"  {path}: {count}")

    return bookmarks
