# AGENTS.md — Bookmarks Cerebro

## Toolchain
- **Package manager**: `uv` (not pip). Install deps: `uv pip install -e ".[dev]"`. Create venv: `uv venv`.
- **Lint / type / format**: `ruff` + `mypy`.
  - ruff: `uv run ruff check src/`, `uv run ruff format --check src/`, `uv run ruff format src/`
  - mypy: `PYTHONPATH=src uv run mypy --explicit-package-bases src/` (must set PYTHONPATH + explicit-package-bases or mypy sees duplicate modules)
- **Tests**: `PYTHONPATH=src uv run pytest tests/ -v --tb=short` (PYTHONPATH required for `from cerebro.X` imports in tests)
- **Pre-commit**: `pre-commit install` (hooks: ruff, mypy, yamllint, file sanity checks)

## Import Rule
- **Always absolute**: `from src.cerebro.X import Y`. Never relative (`from .X import Y`).
- Test files set `sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))` to make `from cerebro.X` work.

## CLI Entry
- Entrypoint: `cerebro` (Click group in `src/cerebro/cli.py`)
- Run module: `PYTHONPATH=src python -m cerebro.cli <command>`
- Full pipeline: `cerebro pipeline bookmarks.html --taxonomy taxonomy.yaml --output-dir data/ --no-ml`
- Dashboard: `cerebro dashboard --host 127.0.0.1 --port 8080`
- Server (extension ingestion): `cerebro serve --host 127.0.0.1 --port 8765`
- Database: `cerebro migrate-db`, `cerebro db-status`
- Config: `cerebro config --config /path/to/.cerebro.toml`

## CI / CD
- **GitHub Actions**: `.github/workflows/ci.yml`
  - Lint job: installs ruff/mypy/yamllint via `uv tool install` (not `uv pip install`), then runs `uvx ruff`, `uvx mypy`
  - Test job: `uv venv` + `uv pip install -e ".[dev]"`, then `uv run pytest`
  - Pipeline-smoke job: runs full pipeline on `.github/testdata/sample.html` and verifies output files exist
- **Clean CI tip**: If lint fails on format, run `uv run ruff format src/` and commit.

## Architecture
- **Source**: `src/cerebro/` — 20+ Python modules. No `__init__.py` complexity; all imports are explicit.
- **Storage**: SQLite via `src/cerebro/db_schema.py` + `src/cerebro/db.py` (`data/cerebro.db`). JSON exports remain available as snapshots.
- **Exports**: `data/vault/` (Obsidian markdown), `data/processed/` (JSON/HTML/CSV/JSONL), `output/` (GEXF).
- **Browser extension**: `browser-extension/` — Manifest V3 with service worker (queue/retry), content script, options page, and popup.
- **Dashboard**: `src/cerebro/dashboard.py` — FastAPI app with Jinja2/htmx templates in `src/cerebro/dashboard_templates/`.
- **Taxonomy**: `taxonomy.yaml` — semantic brain map, ~95 leaf nodes. Loaded by `src/cerebro/taxonomy.py`.
- **Config**: `.cerebro.toml` — per-project settings loaded by `src/cerebro/config.py`.

## Key Files
| File | Purpose |
|------|---------|
| `src/cerebro/cli.py` | Click CLI — all commands and pipeline orchestration |
| `src/cerebro/models.py` | `Bookmark` dataclass — single source of truth for fields |
| `src/cerebro/parser.py` | Netscape HTML → `list[Bookmark]` |
| `src/cerebro/classifier.py` | Hybrid classify: domain rules + keyword rules + ML fallback (KNeighbors + TF-IDF) |
| `src/cerebro/dedup.py` | Duplicate detection: exact / normalized / hash / fuzzy |
| `src/cerebro/enricher.py` | Tag extraction + description generation |
| `src/cerebro/fetcher.py` | Live HTTP fetch + OG tag extraction + dead link detection |
| `src/cerebro/search.py` | TF-IDF + cosine similarity over bookmarks |
| `src/cerebro/server.py` | HTTP ingestion server for browser extension |
| `src/cerebro/crosslinks.py` | Related bookmark discovery |
| `src/cerebro/db_schema.py` | SQLAlchemy Core schema for bookmarks, tags, and audit log |
| `src/cerebro/db.py` | SQLite session context manager + CRUD helpers |
| `src/cerebro/config.py` | `.cerebro.toml` loader + typed `Settings` dataclass |
| `src/cerebro/dashboard.py` | FastAPI app for web dashboard with htmx templates |
| `src/cerebro/dashboard_templates/` | Jinja2 templates (list, detail, stats, partials) |
| `.cerebro.toml` | Per-project configuration template |

## Conventions
- **Dataclass-first**: `Bookmark` is a `@dataclass`. All modules create/modify `Bookmark` objects.
- **JSON I/O**: `src/cerebro/utils.py` provides `load_json()` / `save_json()` with `orjson`.
- **Pipeline pattern**: Every stage takes `list[Bookmark]` → returns `list[Bookmark]`. No mutation in place.
- **File size limit**: Keep files < 200 lines where possible. The repo already has `classifier.py` at 829 lines — that's the exception, not the target.

## Testing
- **Fixture**: `.github/testdata/sample.html` (16 bookmarks) — use for all integration/smoke tests.
- **Test style**: pytest functions, no classes. Import via `sys.path.insert(0, .../src)`.
- **TDD**: Write failing test first, then implementation. Every new module must have a smoke test.

## Git
- **Ignored dirs**: `data/`, `output/`, `__pycache__/`, `*.egg-info/`, `.venv/`, `.omo/`
- **Conventional commits**: `feat:`, `fix:`, `ci:`, `docs:`, `style:`, `test:`
- Do not commit generated artifacts (JSON, HTML, CSV, vault markdown).

## Known Gotchas
1. **mypy duplicate module**: Running `mypy src/` without `PYTHONPATH=src --explicit-package-bases` fails with "Source file found twice". Always use: `PYTHONPATH=src uv run mypy --explicit-package-bases src/`
2. **CI lint job uses `uv tool install`**: Do not install the full package in the lint job — it causes mypy to see both installed `cerebro` and `src.cerebro`. Install only `ruff`, `mypy`, `yamllint` as standalone tools.
3. **Extension popup needs server running**: `cerebro serve` must be active before clicking "Cerebro this page". The server now writes to SQLite, so the dashboard will also see ingested bookmarks.
4. **JSON round-trip loses `fetched_metadata`**: `Bookmark.to_dict()` omits `fetched_metadata`. Use SQLite or `to_full_dict()`/`from_dict()` for complete round-trips.
5. **Server concurrent writes**: Fixed by SQLite. The old JSON-only server had race conditions; the new `server.py` persists via `db.upsert_bookmark`.

## Extension Development
- **Load unpacked**: `chrome://extensions/` → Developer mode → Load unpacked → select `browser-extension/`
- **Permissions needed**: `activeTab`, `storage`, `contextMenus`, `alarms`, `scripting`; `host_permissions: http://localhost:8765/*` and `<all_urls>` for content-script metadata extraction
- **Keyboard shortcut**: `Ctrl+Shift+C` (registered in manifest `commands`)
- **Settings page**: `options.html` — configure host/port via `chrome.storage.local`
- **Offline queue**: Failed ingests are stored in `chrome.storage.local` and retried with exponential backoff via the `drainQueue` alarm

## Docker
- `docker build -t cerebro .` builds a uv-based image
- `docker-compose up` runs the server on `8765` and dashboard on `8080`
- Mount `/app/data` to persist `cerebro.db`
