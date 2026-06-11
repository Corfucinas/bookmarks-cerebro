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
# Install
pip install -e .

# Run the full pipeline
cerebro pipeline bookmarks.html --output ./vault/

# Or step by step
cerebro parse bookmarks.html --output raw.json
cerebro classify raw.json --taxonomy taxonomy.yaml --output classified.json
cerebro enrich classified.json --output enriched.json
cerebro export --obsidian enriched.json --vault-dir ./vault/
cerebro export --html enriched.json --output bookmarks_fixed.html
```

## Taxonomy Philosophy

The default taxonomy is designed as a **semantic brain map** — categories reflect how knowledge actually connects, not arbitrary folder names. Top-level categories include:

- `AI/ML` — models, frameworks, research, tools
- `Programming` — languages, frameworks, patterns, tools
- `Systems` — infrastructure, cloud, DevOps, security
- `Design` — UI/UX, frontend, visualization
- `Research` — papers, references, learning resources
- `Productivity` — workflows, tools, self-hosting
- `Finance` — trading, crypto, quantitative analysis
- `Life` — health, hobbies, travel, personal
- `Hardware` — microcontrollers, IoT, homelab
- `Reference` — documentation, cheatsheets, utilities

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
