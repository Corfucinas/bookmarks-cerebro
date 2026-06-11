# Bookmark Intelligence Pipeline (Bookmarks-Cerebro)

## Overview
Build a Python CLI toolchain (`cerebro`) that parses, enriches, intelligently re-categorizes, and exports 2,334 browser bookmarks into structured data and Obsidian-ready markdown.

## Context
- **Input**: `bookmarks_6_11_26.html` — Netscape Bookmark HTML export from Brave (2,334 bookmarks).
- **Problem**: Bookmarks are poorly categorized (e.g., "AI" folder has 1,242 bookmarks, "Python" has 357, many miscategorized).
- **Goal**: Produce a clean, hierarchical taxonomy (~15 top-level categories), rich metadata per bookmark, and dual exports: Obsidian vault + Netscape HTML for Brave re-import.

---

## Deliverables

| # | Deliverable | Description |
|---|-------------|-------------|
| 1 | `cerebro` Python CLI | Modular CLI tool (parse, categorize, enrich, export). |
| 2 | Clean Taxonomy | YAML-defined hierarchical category tree (max 15 top-level, balanced subs). |
| 3 | Enriched Dataset | JSON dataset (2,334 bookmarks with metadata). |
| 4 | Obsidian Vault | One note per bookmark with YAML frontmatter + tags. |
| 5 | Netscape HTML Export | Re-importable Brave bookmark HTML with correct categories. |
| 6 | GitHub Repo | Public repo with README, `.gitignore`, `requirements.txt`, and reproducible setup. |

---

## Architecture

```
cerebro/
├── src/cerebro/
│   ├── cli.py              # Entrypoint (argparse, subcommands)
│   ├── parser.py           # Netscape HTML → internal datamodel
│   ├── taxonomy.py         # Taxonomy loader, validator, balancer
│   ├── classifier.py       # ML/NLP-based re-categorization
│   ├── enricher.py         # Metadata extraction (domain, tags, description, icon)
│   ├── exporter_json.py    # Serialize enriched bookmarks to JSON
│   ├── exporter_obsidian.py# Markdown vault with YAML frontmatter
│   ├── exporter_html.py    # Netscape HTML re-generation
│   └── utils.py            # Shared helpers (logging, pathing, io)
├── taxonomy.yaml           # Hierarchical category definition
├── data/
│   ├── raw/                # Original HTML export
│   ├── processed/          # Enriched JSON outputs
│   └── vault/              # Obsidian-ready markdown files
├── tests/
│   ├── test_parser.py
│   ├── test_classifier.py
│   ├── test_enricher.py
│   ├── test_exporters.py
│   └── fixtures/           # Sample bookmark HTML snippets
├── README.md
├── requirements.txt
├── pyproject.toml          # Package + build config
└── .gitignore
```

---

## Waves

### Wave 1: Foundation & Parsing

**Objective**: Boot project, define data model, and reliably parse the 2,334 bookmarks.

#### 1.1 Project Bootstrap
- [ ] Create repo skeleton (`pyproject.toml`, `src/cerebro/`, `tests/`, `.gitignore`).
- [ ] Define `Bookmark` dataclass (id, url, title, raw_folder_path, add_date, icon, tags, description, category_breadcrumbs, inferred_metadata).
- [ ] Install dev dependencies (`pytest`, `black`, `ruff`, `mypy`).

**Verification**:
- `python -c "from cerebro.parser import Bookmark; print(Bookmark.__dataclass_fields__.keys())"` runs without error.
- `pytest` runs and discovers the test suite (empty pass OK).

#### 1.2 Netscape HTML Parser
- [ ] Implement `parser.py` to parse `bookmarks_6_11_26.html` using `BeautifulSoup4` or `html.parser`.
- [ ] Handle nested `<DL><DT><A HREF=...>` structure and preserve folder hierarchy.
- [ ] Map `ADD_DATE`, `ICON`, and folder path to `Bookmark` fields.
- [ ] Expose `parse_bookmarks(html_path: str) -> list[Bookmark]`.

**Verification**:
- `python -m cerebro parse --input bookmarks_6_11_26.html --output data/processed/raw_bookmarks.json`
- Assert output JSON has exactly 2,334 entries.
- Spot-check 10 random bookmarks against original HTML for title/URL/folder fidelity.

#### 1.3 Initial Taxonomy Definition
- [ ] Create `taxonomy.yaml` with target ~15 top-level categories (e.g., `AI/ML`, `Programming`, `Design`, `Productivity`, `Reading`, `Career`, `Finance`, `Health`, `Entertainment`, `Reference`, `Self-Hosting`, `Security`, `Hardware`, `Misc`).
- [ ] Allow 2–3 levels deep.
- [ ] Implement `taxonomy.py` to load and validate against schema.

**Verification**:
- `yamllint taxonomy.yaml` passes.
- `python -c "from cerebro.taxonomy import load_taxonomy; t = load_taxonomy('taxonomy.yaml'); assert len(t.roots) <= 15"`

---

### Wave 2: Classification & Categorization

**Objective**: Relabel all 2,334 bookmarks into the clean taxonomy using heuristic + NLP classification.

#### 2.1 Domain-Based Heuristic Classifier
- [ ] Build `classifier.py` with a rules engine mapping domains/substrings to categories.
- [ ] Seed rules from known sources (e.g., `github.com` → Programming, `arxiv.org` → AI/ML, `figma.com` → Design).
- [ ] Handle folders: if all items in a source folder map to one target, lift that signal.

**Verification**:
- Unit tests in `test_classifier.py` assert known URLs land in expected leaves.
- Coverage ≥ 80% for `classifier.py`.

#### 2.2 NLP/Semantic Fallback Classifier
- [ ] Use lightweight NLP (`sentence-transformers/all-MiniLM-L6-v2` or `scikit-learn` TF-IDF + kNN) to classify bookmarks that heuristic rules miss.
- [ ] Training data = the already-classified bookmarks from 2.1.
- [ ] `Bookmark` gets `inferred_category` and `confidence_score`.

**Verification**:
- Confusion matrix on a 10% held-out stratified sample (from heuristically classified set).
- Target macro-F1 ≥ 0.75.

#### 2.3 Taxonomy Balancing
- [ ] After first-pass classification, compute category histograms.
- [ ] If a leaf or branch exceeds 200 items, run a sub-clustering pass to suggest splits.
- [ ] If a leaf has < 5 items, suggest merge up to parent.
- [ ] Emit `taxonomy_rebalanced.yaml` and `category_histogram.json`.

**Verification**:
- No top-level category exceeds 25% of total bookmarks.
- No leaf category exceeds 300 bookmarks (post-split).
- All 2,334 bookmarks have a non-null `category_breadcrumbs`.

---

### Wave 3: Metadata Enrichment

**Objective**: Augment every bookmark with rich, usable metadata.

#### 3.1 Core Metadata Extraction
- [ ] Extract: domain (TLD+1), parsed title (from HTML or fallback to bookmark title).
- [ ] Infer: language of content (via `langdetect` or URL heuristics).
- [ ] Normalize: `add_date` to ISO 8601 from Unix epoch in `ADD_DATE` attribute.

**Verification**:
- Random sample of 20 bookmarks: manual inspection of domain/title/date correctness.
- All 2,334 records have non-empty `domain` and `add_date_iso`.

#### 3.2 Tag Inference
- [ ] Derive tags from URL path segments, query params, and page title keywords.
- [ ] Use keyword extraction (`rake-nltk` or `yake`) on bookmark titles/descriptions.
- [ ] Cross-reference with taxonomy leaves for additional tags.
- [ ] Store tags as lowercase, hyphenated, deduplicated list.

**Verification**:
- Average tags per bookmark ≥ 3, median ≥ 4.
- No empty tag arrays.

#### 3.3 Description Generation
- [ ] Attempt meta-description extraction (async HTTP fetch, 3s timeout).
- [ ] On failure / timeout, generate a synthetic description from: domain, title, tags, and inferred category.
- [ ] Cache fetched descriptions to `data/cache/` (respect robots, don’t hammer).

**Verification**:
- Fetch success rate ≥ 40% (given mixed domains and paywalls).
- All bookmarks have `description` (synthetic or real).
- No `description` exceeds 500 characters.

---

### Wave 4: Export Pipelines

**Objective**: Produce the final dual-format outputs.

#### 4.1 JSON Data Export
- [ ] Serialize the fully enriched dataset to `data/processed/enriched_bookmarks.json`.
- [ ] Pretty-printed, gzip-compressed backup at `enriched_bookmarks.json.gz`.

**Verification**:
- JSON validates against `jsonschema` schema.
- `jq 'length'` returns 2334.
- Gunzip and diff against original: IDs and URLs are 1:1.

#### 4.2 Obsidian Vault Export
- [ ] One file per bookmark: `vault/<category>/<safe-title>.md`.
- [ ] Frontmatter: YAML block with `id`, `url`, `title`, `tags`, `category`, `date_added`, `description`, `icon`.
- [ ] Body: Brief description, link to URL, breadcrumb trail, auto-generated backlinks section for related bookmarks in same category.
- [ ] Tags rendered as `#tag` inline.

**Verification**:
- `find vault/ -name "*.md" | wc -l` == 2334.
- `yamllint` on 5 random files: frontmatter parses cleanly.
- Markdown renders without broken YAML in Obsidian (simulated via `python-frontmatter`).

#### 4.3 Netscape HTML Export
- [ ] Reverse engineer Netscape format: nested `<DL>` structure per final taxonomy.
- [ ] Preserve `ADD_DATE` and `ICON` where available.
- [ ] Output: `bookmarks_cerebro_reorganized.html`.

**Verification**:
- Re-import into a fresh Brave profile succeeds without errors.
- Folder structure mirrors taxonomy YAML.
- Total bookmark count after import == 2334.

---

### Wave 5: CLI Polish & GitHub Hosting

**Objective**: Make the tool reusable, documented, and public.

#### 5.1 CLI Integration
- [ ] `cerebro parse <input>` → raw JSON.
- [ ] `cerebro classify <raw.json>` → enriched JSON.
- [ ] `cerebro enrich <enriched.json>` → fetch descriptions, tags.
- [ ] `cerebro export --obsidian <enriched.json>` → vault.
- [ ] `cerebro export --html <enriched.json>` → HTML.
- [ ] `cerebro pipeline <input.html>` → run all steps end-to-end.
- [ ] Config file support: `cerebro.yaml` for taxonomy path, API keys, cache dirs.

**Verification**:
- `--help` prints all subcommands.
- End-to-end pipeline runs on `bookmarks_6_11_26.html` in under 5 minutes (local CPU).
- Exit codes: 0 = success, 1 = validation/parse error, 2 = network failure.

#### 5.2 Repo & Documentation
- [ ] `README.md`: overview, installation, quickstart, taxonomy philosophy, architecture diagram, contributing.
- [ ] `requirements.txt` + `pyproject.toml`.
- [ ] `.gitignore` for Python, caches, data/outputs.
- [ ] GitHub Actions CI: lint (`ruff`, `mypy`), test (`pytest`), build check.
- [ ] MIT License.

**Verification**:
- `pip install -e .` succeeds in a fresh venv.
- CI badge green on `main`.
- `python -m cerebro --version` prints version.

---

## Verification Criteria Summary

| Step | Criteria |
|------|----------|
| Parse | 2334 bookmarks parsed; titles/URLs match source. |
| Classify | All bookmarks have category; macro-F1 ≥ 0.75 on holdout. |
| Balance | No top-level > 25%; no leaf > 300 items. |
| Enrich | All bookmarks have domain, date, tags (≥3 avg), description. |
| JSON Export | Valid JSON; count = 2334. |
| Obsidian Export | 2334 `.md` files; YAML frontmatter valid. |
| HTML Export | Re-imports cleanly into Brave; count = 2334. |
| CLI | `--help` works; pipeline runs end-to-end. |
| Repo | README, CI green, MIT license. |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| HTML parsing edge cases (malformed anchors, missing titles) | BeautifulSoup4 with strict+lenient fallback; log warnings. |
| Network fetches slow / blocked | Async `aiohttp` with semaphore=20, 3s timeout, aggressive caching. |
| Overly aggressive re-categorization | Confidence threshold (discard < 0.6); allow manual overrides in `overrides.yaml`. |
| Taxonomy feels generic | Design taxonomy as "my brain map": use connected, semantic category names (e.g., "AI/ML → Models → Diffusion", "Self-Hosting → Homelab"). |
| Performance with 2334 HTTP requests | Batch + async; skip by default if `--no-fetch`; rely on synthetic descriptions. |

---

## Mode
**Standard** (horizontal layers, not MVP slices) — this is a toolchain with discrete stages rather than a vertical feature slice.

## Notes
- The taxonomy should feel **semantic and personal** — "looking into my brain." Avoid sterile names like `Folder01`; prefer evocative, connected labels.
- Keep the classifier lightweight. We want it to run locally without GPU dependency. `scikit-learn` + `sentence-transformers` (CPU) is fine.
- Obsidian vault can be opened directly as a folder in Obsidian; no plugin dependency needed.
