# Bookmarks Cerebro 🧠

> **Turn your browser bookmarks into a rich, semantic knowledge map.**

Bookmarks Cerebro parses, intelligently re-categorizes, and enriches your browser bookmarks into a structured dataset — then exports them as an Obsidian-ready vault, clean Netscape HTML, CSV, JSONL, or a searchable index.

## Features

- **📖 Parse**: Read Netscape Bookmark HTML exports (Chrome, Brave, Firefox)
- **🧠 Categorize**: ML-assisted intelligent re-categorization into a clean, balanced taxonomy
- **🔍 Dedup**: Exact, normalized, hash-based, or fuzzy title-similarity duplicate detection
- **🔗 Cross-links**: Discover related bookmarks by domain overlap, shared tags, URL mentions, and category proximity
- **🏷️ Enrich**: Domain extraction, tag inference, description generation, Open Graph metadata
- **🌐 Live Fetch**: HEAD/GET page fetching with OG tag extraction and dead-link flagging
- **📤 Export**: Obsidian vault + Netscape HTML + JSON + JSONL + CSV + tag co-occurrence GEXF
- **🔎 Semantic Search**: TF-IDF + cosine similarity over titles, tags, descriptions, and categories
- **🖥️ Local Server**: HTTP endpoint for browser-extension ingestion (`POST /api/ingest`)
- **🔌 Browser Extension**: Chrome/Brave popup to "Cerebro this page" — classify, enrich, and append instantly
- **📦 Git Vault**: Auto-commit and push your Obsidian vault to git
- **⚡ CLI**: Single-command pipeline and granular subcommands

## Quickstart

```bash
# Install with uv (recommended)
uv pip install -e ".[dev]"

# Run the full pipeline
cerebro pipeline bookmarks.html --output ./vault/

# With live fetch + dead link detection
cerebro pipeline bookmarks.html --fetch-live --check-dead

# Or step by step
cerebro parse bookmarks.html --output raw.json
cerebro classify raw.json --taxonomy taxonomy.yaml --output classified.json
cerebro dedup classified.json --mode normalized --output deduped.json
cerebro crosslinks deduped.json --output linked.json
cerebro enrich linked.json --output enriched.json
cerebro export --obsidian enriched.json --vault-dir ./vault/
cerebro export --html enriched.json --output bookmarks_fixed.html
cerebro export --jsonl enriched.json --output bookmarks.jsonl
cerebro export --csv enriched.json --output bookmarks.csv

# Search your enriched collection
cerebro search enriched.json "rust async patterns" --top-k 10

# Start the ingestion server for the browser extension
cerebro serve --host 127.0.0.1 --port 8765

# Build and export tag co-occurrence graph
cerebro tag-graph enriched.json --output tags.gexf

# Push Obsidian vault to git
cerebro git-push --vault-dir ./vault/ --remote origin --branch main
```

## Taxonomy

The default taxonomy is designed as a **semantic brain map** — categories reflect how knowledge actually connects, not arbitrary folder names. Top-level categories include:

- `AI` — models, frameworks, research, tools, ethics, hardware
- `Data` — databases, pipelines, analytics, visualization
- `Programming` — languages, paradigms, patterns, testing
- `Web` — frontend, backend, APIs, mobile, browsers
- `Systems` — cloud, containers, Linux, networking, observability
- `Security` — cryptography, AppSec, OSINT, blue/red team
- `Quant` — strategies, portfolio, derivatives, risk
- `Blockchain` — Ethereum, Bitcoin, DeFi, NFTs, DAOs
- `Hardware` — microcontrollers, IoT, robotics, fabrication
- `Career` — interview, resume, freelancing, startups
- `Learning` — tutorials, courses, papers, books, documentation
- `Design` — UI/UX, 3D, photo/video, music, typography
- `Productivity` — PKM, editors, terminal, automation, self-hosting
- `Life` — health, food, travel, hobbies, relationships
- `Entertainment` — games, streaming, social media, podcasts
- `Reference` — Wikipedia, utilities, search, legal

## Architecture

```
cerebro/
├── parse        → Netscape HTML → structured JSON
├── classify     → heuristic + NLP categorization
├── dedup        → exact | normalized | hash | fuzzy duplicate detection
├── crosslinks   → related bookmarks by domain, tags, URL mentions, category
├── fetch        → live page fetch + OG tags + dead link check
├── enrich       → metadata extraction + tag inference + description generation
├── search       → TF-IDF semantic search over enriched bookmarks
├── server       → local HTTP server for browser-extension ingestion
├── export       → JSON | JSONL | CSV | Obsidian | Netscape HTML | GEXF
└── cli          → Click-based CLI with pipeline + granular subcommands
```

## Browser Extension

The `browser-extension/` directory contains a Manifest V3 Chrome/Brave extension:

1. Open `chrome://extensions/`
2. Enable **Developer mode**
3. Click **Load unpacked** and select `browser-extension/`
4. Click the Cerebro icon on any page to classify, enrich, and append it to your vault instantly

## License

MIT
