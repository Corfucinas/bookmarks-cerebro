"""Hybrid bookmark classifier: domain heuristics + keyword matching + ML fallback."""

from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import KNeighborsClassifier

from src.cerebro.models import Bookmark
from src.cerebro.taxonomy import load_taxonomy
from src.cerebro.utils import extract_tld_plus_one

logger = logging.getLogger("cerebro")

# Domain → category mapping (high confidence)
DOMAIN_RULES: dict[str, list[str]] = {
    "github.com": ["Programming", "DevEx"],
    "stackoverflow.com": ["Programming", "DevEx"],
    "gitlab.com": ["Programming", "DevEx"],
    "arxiv.org": ["Learning", "Papers"],
    "paperswithcode.com": ["AI", "Research"],
    "huggingface.co": ["AI", "Tools"],
    "pytorch.org": ["AI", "Tools"],
    "tensorflow.org": ["AI", "Tools"],
    "kaggle.com": ["AI", "Tools"],
    "figma.com": ["Design", "UI-UX"],
    "dribbble.com": ["Design", "UI-UX"],
    "awwwards.com": ["Design", "UI-UX"],
    "aws.amazon.com": ["Systems", "Cloud"],
    "cloud.google.com": ["Systems", "Cloud"],
    "azure.microsoft.com": ["Systems", "Cloud"],
    "docker.com": ["Systems", "Containers"],
    "kubernetes.io": ["Systems", "Containers"],
    "torproject.org": ["Security", "Privacy"],
    "medium.com": ["Learning", "Tutorials"],
    "dev.to": ["Programming", "DevEx"],
    "freecodecamp.org": ["Learning", "Courses"],
    "coursera.org": ["Learning", "Courses"],
    "udemy.com": ["Learning", "Courses"],
    "youtube.com": ["Learning", "Tutorials"],
    "twitter.com": ["Entertainment", "Social-Media"],
    "x.com": ["Entertainment", "Social-Media"],
    "reddit.com": ["Entertainment", "Social-Media"],
    "linkedin.com": ["Career", "Networking"],
    "indeed.com": ["Career", "Interview"],
    "glassdoor.com": ["Career", "Interview"],
    "coinbase.com": ["Quant", "Crypto-Trading"],
    "binance.com": ["Quant", "Crypto-Trading"],
    "etherscan.io": ["Blockchain", "Ethereum"],
    "coingecko.com": ["Quant", "Crypto-Trading"],
    "tradingview.com": ["Quant", "Strategies"],
    "investopedia.com": ["Learning", "Documentation"],
    "wikipedia.org": ["Reference", "Wikipedia"],
    "w3schools.com": ["Learning", "Cheatsheets"],
    "mdn.mozilla.org": ["Learning", "Documentation"],
    "caniuse.com": ["Web", "Web-Standards"],
    "npmjs.com": ["Programming", "DevEx"],
    "pypi.org": ["Programming", "Languages"],
    "crates.io": ["Programming", "Languages"],
    "news.ycombinator.com": ["Entertainment", "News"],
    "producthunt.com": ["Career", "Startups"],
    "angel.co": ["Career", "Startups"],
    "kickstarter.com": ["Career", "Startups"],
    "arduino.cc": ["Hardware", "Microcontrollers"],
    "raspberrypi.org": ["Hardware", "SBC"],
    "adafruit.com": ["Hardware", "Electronics"],
    "sparkfun.com": ["Hardware", "Electronics"],
    "expedia.com": ["Life", "Travel"],
    "booking.com": ["Life", "Travel"],
    "tripadvisor.com": ["Life", "Travel"],
    "allrecipes.com": ["Life", "Food"],
    "foodnetwork.com": ["Life", "Food"],
    "myfitnesspal.com": ["Life", "Health"],
    "strava.com": ["Life", "Health"],
    "spotify.com": ["Entertainment", "Streaming"],
    "soundcloud.com": ["Entertainment", "Streaming"],
    "ultimate-guitar.com": ["Life", "Hobbies"],
    "obsidian.md": ["Productivity", "PKM"],
    "notion.so": ["Productivity", "PKM"],
    "trello.com": ["Productivity", "Automation"],
    "proton.me": ["Security", "Privacy"],
    "eff.org": ["Security", "Privacy"],
    "nmap.org": ["Security", "Red-Team"],
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
            "model",
            "training",
            "inference",
            "embedding",
            "vector",
        ],
        ["AI", "Deep-Learning"],
        0.85,
    ),
    (
        [
            "transformer",
            "llm",
            "gpt",
            "rag",
            "fine-tune",
            "prompt",
            "openai",
            "anthropic",
            "claude",
        ],
        ["AI", "LLMs"],
        0.90,
    ),
    (
        ["diffusion", "gan", "vae", "image generation", "synthetic", "generative"],
        ["AI", "Generative-AI"],
        0.90,
    ),
    (
        ["pytorch", "tensorflow", "jax", "huggingface", "onnx", "caffe"],
        ["AI", "Tools"],
        0.85,
    ),
    (
        [
            "computer vision",
            "opencv",
            "image recognition",
            "object detection",
            "segmentation",
            "ocr",
        ],
        ["AI", "Computer-Vision"],
        0.90,
    ),
    (
        [
            "reinforcement learning",
            "rl",
            "q-learning",
            "policy gradient",
            "agent",
            "multi-armed bandit",
        ],
        ["AI", "Reinforcement-Learning"],
        0.90,
    ),
    (
        ["nlp", "natural language processing", "sentiment", "ner", "tokenization", "bert"],
        ["AI", "NLP"],
        0.90,
    ),
    (
        ["mlops", "feature store", "model serving", "model monitoring", "experiment tracking"],
        ["AI", "MLOps"],
        0.85,
    ),
    (
        [
            "quantitative",
            "backtest",
            "algorithmic trading",
            "trading strategy",
            "sharpe",
            "alpha",
            "beta",
            "factor",
        ],
        ["Quant", "Strategies"],
        0.90,
    ),
    (
        ["portfolio", "asset allocation", "risk parity", "modern portfolio theory"],
        ["Quant", "Portfolio"],
        0.85,
    ),
    (
        ["derivatives", "options", "futures", "swap", "black-scholes", "greeks"],
        ["Quant", "Derivatives"],
        0.90,
    ),
    (
        ["execution", "market impact", "slippage", "order routing", "twap", "vwap"],
        ["Quant", "Execution"],
        0.85,
    ),
    (
        ["risk", "var", "cvar", "stress test", "drawdown", "scenario analysis"],
        ["Quant", "Risk"],
        0.85,
    ),
    (
        ["ethereum", "solidity", "evm", "ethers", "hardhat", "foundry"],
        ["Blockchain", "Ethereum"],
        0.90,
    ),
    (
        ["bitcoin", "lightning network", "taproot", "btc", "satoshi"],
        ["Blockchain", "Bitcoin"],
        0.90,
    ),
    (
        ["defi", "dex", "amm", "liquidity pool", "yield farming", "flash loan", "lending protocol"],
        ["Blockchain", "DeFi"],
        0.90,
    ),
    (
        ["nft", "erc-721", "erc-1155", "marketplace", "digital collectible"],
        ["Blockchain", "NFTs"],
        0.90,
    ),
    (
        ["dao", "governance", "treasury", "proposal", "snapshot", "token holder"],
        ["Blockchain", "DAOs"],
        0.85,
    ),
    (
        ["smart contract", "tokenomics", "whitepaper", "consensus", "layer 2", "rollup"],
        ["Blockchain", "Infrastructure"],
        0.80,
    ),
    (
        ["docker", "kubernetes", "k8s", "container", "helm", "pod", "microservice"],
        ["Systems", "Containers"],
        0.85,
    ),
    (
        [
            "aws",
            "gcp",
            "azure",
            "serverless",
            "lambda",
            "cloud",
            "s3",
            "ec2",
            "terraform",
            "pulumi",
        ],
        ["Systems", "Cloud"],
        0.85,
    ),
    (
        ["linux", "ubuntu", "debian", "arch", "gentoo", "kernel", "systemd", "bash", "shell"],
        ["Systems", "Linux"],
        0.85,
    ),
    (
        ["cryptography", "encryption", "cipher", "hash", "rsa", "aes", "ecdsa", "zk-snark"],
        ["Security", "Cryptography"],
        0.90,
    ),
    (
        ["tor", "vpn", "privacy", "anonymity", "signal", "pgp"],
        ["Security", "Privacy"],
        0.85,
    ),
    (
        ["pentest", "penetration test", "exploit", "cve", "vulnerability", "metasploit", "burp"],
        ["Security", "Red-Team"],
        0.85,
    ),
    (
        ["appsec", "owasp", "sast", "dast", "dependency scan", "secure coding"],
        ["Security", "AppSec"],
        0.85,
    ),
    (
        ["malware", "reverse engineering", "forensics", "yara", "sandbox"],
        ["Security", "Malware"],
        0.85,
    ),
    (
        ["blue team", "siem", "soar", "incident response", "threat hunting", "defense"],
        ["Security", "Blue-Team"],
        0.85,
    ),
    (
        [
            "css",
            "html",
            "javascript",
            "react",
            "vue",
            "svelte",
            "angular",
            "frontend",
            "ui",
            "ux",
            "responsive",
            "tailwind",
            "bootstrap",
            "sass",
        ],
        ["Web", "Frontend"],
        0.80,
    ),
    (
        [
            "backend",
            "api",
            "rest",
            "graphql",
            "grpc",
            "server",
            "microservice",
            "fastapi",
            "django",
            "flask",
            "nestjs",
        ],
        ["Web", "Backend"],
        0.80,
    ),
    (
        ["next.js", "nuxt", "fullstack", "ssr", "ssg", "jamstack"],
        ["Web", "Fullstack"],
        0.80,
    ),
    (
        ["mobile", "ios", "android", "react native", "flutter", "swift", "kotlin"],
        ["Web", "Mobile"],
        0.80,
    ),
    (
        ["browser", "chrome", "firefox", "webkit", "v8", "extension", "pwa"],
        ["Web", "Browsers"],
        0.80,
    ),
    (
        ["figma", "sketch", "design system", "wireframe", "prototype"],
        ["Design", "UI-UX"],
        0.85,
    ),
    (
        ["adobe", "photoshop", "illustrator", "indesign", "creative suite", "graphic"],
        ["Design", "Graphic-Design"],
        0.85,
    ),
    (
        ["blender", "3d model", "render", "unreal", "unity", "cad", "maya"],
        ["Design", "3D"],
        0.85,
    ),
    (
        ["video edit", "premiere", "davinci", "after effects", "color grade", "compositing"],
        ["Design", "Photo-Video"],
        0.85,
    ),
    (
        ["music production", "daw", "ableton", "fl studio", "logic pro", "composition"],
        ["Design", "Music"],
        0.80,
    ),
    (
        ["python", "django", "fastapi", "flask", "pandas", "numpy", "scipy"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["rust", "cargo", "tokio", "actix", "axum", "serde"],
        ["Programming", "Languages"],
        0.85,
    ),
    (
        ["golang", "go lang", "gin", "echo"],
        ["Programming", "Languages"],
        0.85,
    ),
    (
        ["typescript", "node.js", "nodejs", "express", "nestjs", "bun"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["java", "spring", "jvm", "kotlin", "gradle", "maven"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["c++", "cpp", "cmake", "qt", "boost"],
        ["Programming", "Languages"],
        0.80,
    ),
    (
        ["haskell", "purescript", "elm", "functional programming", "monad"],
        ["Programming", "Paradigms"],
        0.85,
    ),
    (
        ["sql", "database", "postgres", "mysql", "sqlite", "orm", "query", "prisma", "sqlalchemy"],
        ["Data", "Databases"],
        0.80,
    ),
    (
        ["etl", "pipeline", "airflow", "dagster", "data warehouse", "lake"],
        ["Data", "Data-Engineering"],
        0.80,
    ),
    (
        ["analytics", "bi", "dashboard", "tableau", "looker", "metabase"],
        ["Data", "Analytics"],
        0.80,
    ),
    (
        ["visualization", "chart", "plot", "d3", "matplotlib", "plotly", "vega"],
        ["Data", "Visualization"],
        0.80,
    ),
    (
        ["big data", "spark", "hadoop", "kafka", "stream processing", "distributed"],
        ["Data", "Big-Data"],
        0.85,
    ),
    (
        ["time series", "forecasting", "arima", "prophet", "anomaly detection"],
        ["Data", "Time-Series"],
        0.85,
    ),
    (
        ["data science", "exploratory analysis", "feature engineering", "eda"],
        ["Data", "Data-Science"],
        0.80,
    ),
    (
        ["devops", "ci/cd", "jenkins", "github actions", "gitlab ci", "argo"],
        ["Programming", "DevEx"],
        0.80,
    ),
    (
        ["test", "testing", "pytest", "unittest", "mock", "tdd", "bdd", "fuzz"],
        ["Programming", "Testing"],
        0.75,
    ),
    (
        ["algorithm", "leetcode", "dynamic programming", "graph", "sorting", "complexity"],
        ["Programming", "Algorithms"],
        0.80,
    ),
    (
        ["design pattern", "refactor", "clean code", "solid", "dry", "kiss"],
        ["Programming", "Patterns"],
        0.75,
    ),
    (
        ["performance", "optimization", "profiling", "benchmark", "concurrency", "parallel"],
        ["Programming", "Performance"],
        0.80,
    ),
    (
        ["monitoring", "logging", "tracing", "prometheus", "grafana", "jaeger", "otel"],
        ["Systems", "Observability"],
        0.80,
    ),
    (
        ["interview", "leetcode", "system design", "coding interview", "behavioral"],
        ["Career", "Interview"],
        0.85,
    ),
    (
        ["resume", "cv", "portfolio", "linkedin", "personal brand"],
        ["Career", "Resume"],
        0.80,
    ),
    (
        ["freelance", "upwork", "fiverr", "contract", "client", "consulting"],
        ["Career", "Freelancing"],
        0.80,
    ),
    (
        ["startup", "business", "marketing", "seo", "growth", "product", "pitch"],
        ["Career", "Startups"],
        0.75,
    ),
    (
        ["leadership", "management", "delegate", "hiring", "1:1", "team"],
        ["Career", "Leadership"],
        0.75,
    ),
    (
        ["arduino", "esp32", "stm32", "avr", "pic", "firmware"],
        ["Hardware", "Microcontrollers"],
        0.85,
    ),
    (
        ["raspberry pi", "jetson", "coral", "embedded linux"],
        ["Hardware", "SBC"],
        0.85,
    ),
    (
        ["pcb", "circuit", "component", "solder", "oscilloscope", "multimeter"],
        ["Hardware", "Electronics"],
        0.80,
    ),
    (
        ["iot", "mqtt", "lora", "sensor", "smart home", "zigbee"],
        ["Hardware", "IoT"],
        0.85,
    ),
    (
        ["robotics", "ros", "actuator", "kinematics", "slam", "gazebo"],
        ["Hardware", "Robotics"],
        0.85,
    ),
    (
        ["3d print", "cnc", "laser cut", "fabrication", "maker"],
        ["Hardware", "Fabrication"],
        0.80,
    ),
    (
        ["obsidian", "zettelkasten", "pkm", "note-taking", "second brain"],
        ["Productivity", "PKM"],
        0.80,
    ),
    (
        ["vim", "neovim", "emacs", "vscode", "ide", "editor"],
        ["Productivity", "Editors"],
        0.80,
    ),
    (
        ["tmux", "zsh", "fish", "terminal", "shell", "cli", "dotfiles"],
        ["Productivity", "Terminal"],
        0.80,
    ),
    (
        ["script", "bot", "n8n", "make", "zapier", "cron", "workflow automation"],
        ["Productivity", "Automation"],
        0.75,
    ),
    (
        ["self-host", "homelab", "nas", "proxmox", "nextcloud", "pi-hole"],
        ["Productivity", "Self-Hosting"],
        0.85,
    ),
    (
        ["rss", "newsletter", "read-later", "pocket", "instapaper", "annotation"],
        ["Productivity", "Reading"],
        0.75,
    ),
    (
        ["guitar", "tab", "chord", "song", "sheet music"],
        ["Life", "Hobbies"],
        0.80,
    ),
    (
        ["game", "gaming", "steam", "speedrun", "mod", "esports"],
        ["Entertainment", "Games"],
        0.80,
    ),
    (
        ["movie", "tv", "anime", "documentary", "netflix", "streaming"],
        ["Entertainment", "Streaming"],
        0.75,
    ),
    (
        ["travel", "destination", "hotel", "flight", "trip", "vacation", "hiking"],
        ["Life", "Travel"],
        0.80,
    ),
    (
        ["recipe", "cooking", "food", "restaurant", "cuisine", "baking"],
        ["Life", "Food"],
        0.80,
    ),
    (
        ["fitness", "workout", "gym", "nutrition", "health", "diet", "sleep"],
        ["Life", "Health"],
        0.80,
    ),
    (
        ["paper", "arxiv", "journal", "academic", "scientific", "publication", "conference"],
        ["Learning", "Papers"],
        0.85,
    ),
    (
        ["course", "tutorial", "learn", "mooc", "class", "lesson", "bootcamp", "udemy"],
        ["Learning", "Courses"],
        0.75,
    ),
    (
        ["book", "novel", "literature", "reading", "author", "goodreads"],
        ["Learning", "Books"],
        0.75,
    ),
    (
        ["cheatsheet", "reference", "docs", "documentation", "manual", "guide", "wiki"],
        ["Learning", "Documentation"],
        0.75,
    ),
    (
        ["wikipedia", "encyclopedia"],
        ["Reference", "Wikipedia"],
        0.90,
    ),
    (
        ["osint", "intelligence", "reconnaissance", "investigation", "shodan", "maltego"],
        ["Security", "OSINT"],
        0.85,
    ),
    (
        ["network", "protocol", "tcp/ip", "http", "dns", "firewall", "router", "bgp", "cdn"],
        ["Systems", "Networking"],
        0.80,
    ),
    (
        ["compliance", "soc2", "iso27001", "gdpr", "hipaa", "audit", "pci"],
        ["Security", "Compliance"],
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
            "coding/sql": ["Data", "Databases"],
            "coding/yaml": ["Programming", "DevEx"],
            "coding/frontend": ["Web", "Frontend"],
            "coding/mobile": ["Web", "Mobile"],
            "coding/dev tools": ["Programming", "DevEx"],
            "coding/github": ["Programming", "DevEx"],
            "coding/linux": ["Systems", "Linux"],
            "coding/linux/security": ["Security", "Blue-Team"],
            "coding/cryptography": ["Security", "Cryptography"],
            "coding/best practices": ["Programming", "Patterns"],
            "coding/machine learning": ["AI", "Deep-Learning"],
            "quantitative trading": ["Quant", "Strategies"],
            "cryptocurrency": ["Blockchain", "DeFi"],
            "hacking": ["Security", "Red-Team"],
            "steganography": ["Security", "Cryptography"],
            "osint": ["Security", "OSINT"],
            "guitar": ["Life", "Hobbies"],
            "study": ["Learning", "Courses"],
            "personal": ["Life", "Relationships"],
            "travel": ["Life", "Travel"],
            "games": ["Entertainment", "Games"],
            "bodybuilding": ["Life", "Health"],
            "plants": ["Life", "Hobbies"],
            "docker": ["Systems", "Containers"],
            "kubernetes": ["Systems", "Containers"],
            "microservices": ["Systems", "Containers"],
            "nginx": ["Systems", "Networking"],
            "cloud architecture": ["Systems", "Cloud"],
            "api": ["Web", "APIs"],
            "http": ["Web", "Web-Standards"],
            "asyncio": ["Programming", "Paradigms"],
            "webscrapping": ["Programming", "DevEx"],
            "interview": ["Career", "Interview"],
            "barclays": ["Quant", "Execution"],
            "banking": ["Quant", "Execution"],
            "consultant": ["Career", "Startups"],
            "freelancing": ["Career", "Freelancing"],
            "gentoo": ["Systems", "Linux"],
            "arch": ["Systems", "Linux"],
            "vim": ["Productivity", "Editors"],
            "tmux": ["Productivity", "Terminal"],
            "vscode": ["Programming", "DevEx"],
            "monitoring": ["Systems", "Observability"],
            "tracing": ["Systems", "Observability"],
            "analytics": ["Data", "Analytics"],
            "indicators": ["Quant", "Strategies"],
            "strategies": ["Quant", "Strategies"],
            "flash loans eth": ["Blockchain", "DeFi"],
            "dex": ["Blockchain", "DeFi"],
            "solidity": ["Blockchain", "Ethereum"],
            "arduino": ["Hardware", "Microcontrollers"],
            "microcontroller": ["Hardware", "Microcontrollers"],
            "opencv": ["AI", "Computer-Vision"],
            "react": ["Web", "Frontend"],
            "wikipedia": ["Reference", "Wikipedia"],
            "documentation": ["Learning", "Documentation"],
            "obsidian": ["Productivity", "PKM"],
            "fastapi": ["Web", "Backend"],
            "django": ["Web", "Backend"],
            "pandas": ["Data", "Data-Science"],
            "cython": ["Programming", "Languages"],
            "pysqlite": ["Data", "Databases"],
            "regexp": ["Programming", "Patterns"],
            "linting": ["Programming", "DevEx"],
            "pytest": ["Programming", "Testing"],
            "openai": ["AI", "LLMs"],
            "langchain": ["AI", "Tools"],
            "chemistry": ["Learning", "Science"],
            "mathematics": ["Learning", "Math"],
            "stadistics": ["Learning", "Math"],
            "harvard": ["Learning", "Courses"],
            "oxford": ["Learning", "Courses"],
            "memorization": ["Learning", "Tutorials"],
            "viewfin": ["Quant", "Research"],
            "raspberry pi": ["Hardware", "SBC"],
            "betterment": ["Life", "Personal-Finance"],
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
            x_matrix = self.vectorizer.transform([text])
            proba = self.ml_classifier.predict_proba(x_matrix)[0]
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
        x_matrix = self.vectorizer.fit_transform(classified)
        self.ml_classifier = KNeighborsClassifier(n_neighbors=5, weights="distance")
        self.ml_classifier.fit(x_matrix, labels)
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
