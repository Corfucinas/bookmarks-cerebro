# Bookmarks Cerebro 🧠

> **Turn your browser bookmarks into a rich, semantic knowledge map.**

Bookmarks Cerebro parses, intelligently re-categorizes, and enriches your browser bookmarks into a structured dataset — then exports them as an Obsidian-ready vault or a clean Netscape HTML file for re-import.

## Features

- **📖 Parse**: Read Netscape Bookmark HTML exports (Chrome, Brave, Firefox)
- **🧠 Categorize**: ML-assisted intelligent re-categorization into a clean, balanced taxonomy
- **🏷️ Enrich**: Domain extraction, tag inference, description generation
- **📤 Export**: Obsidian markdown vault + Netscape HTML for Brave/Chrome re-import
- **⚡ CLI**: Single-command pipeline: `cerebro pipeline bookmarks.html`

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
cerebro enrich classified.json --output enriched.json
cerebro export --obsidian enriched.json --vault-dir ./vault/
cerebro export --html enriched.json --output bookmarks_fixed.html
```

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

## New Enrichment Features

- **Duplicate detection** — exact-URL deduplication with alias preservation
- **Live page fetch** — HEAD/GET with Open Graph tag extraction
- **Dead link detection** — 404/410/500 flagged; soft-dead (403/429) noted
- **Cross-link suggestions** — related bookmarks by category, domain, and temporal co-occurrence

## Architecture

```
cerebro/
├── parse      → Netscape HTML → structured JSON
├── classify   → heuristic + NLP categorization
├── dedup      → exact-URL duplicate detection
├── fetch      → live page fetch + OG tags + dead link check
├── enrich     → metadata extraction + tag inference
└── export     → JSON / Obsidian / Netscape HTML
```
## Architecture

```
cerebro/
├── parse      → Netscape HTML → structured JSON
├── classify   → heuristic + NLP categorization
├── enrich     → metadata extraction + tag inference
└── export     → JSON / Obsidian / Netscape HTML
```

## License

MIT
