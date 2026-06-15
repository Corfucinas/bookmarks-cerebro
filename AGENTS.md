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
- Dashboard (planned): `cerebro dashboard --host 127.0.0.1 --port 8080`
- Server (extension ingestion): `cerebro serve --host 127.0.0.1 --port 8765`

## CI / CD
- **GitHub Actions**: `.github/workflows/ci.yml`
  - Lint job: installs ruff/mypy/yamllint via `uv tool install` (not `uv pip install`), then runs `uvx ruff`, `uvx mypy`
  - Test job: `uv venv` + `uv pip install -e ".[dev]"`, then `uv run pytest`
  - Pipeline-smoke job: runs full pipeline on `.github/testdata/sample.html` and verifies output files exist
- **Clean CI tip**: If lint fails on format, run `uv run ruff format src/` and commit.

## Architecture
- **Source**: `src/cerebro/` — 18+ Python modules. No `__init__.py` complexity; all imports are explicit.
- **Storage**: Currently JSON files (`data/processed/*.json`). Planned migration to SQLite.
- **Exports**: `data/vault/` (Obsidian markdown), `data/processed/` (JSON/HTML/CSV/JSONL), `output/` (GEXF).
- **Browser extension**: `browser-extension/` — Manifest V3 popup that POSTs to `localhost:8765/api/ingest`.
- **Taxonomy**: `taxonomy.yaml` — semantic brain map, ~95 leaf nodes. Loaded by `src/cerebro/taxonomy.py`.

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
| `src/cerebro/db.py` | **Planned**: SQLite schema + connection (not yet created) |
| `src/cerebro/dashboard.py` | **Planned**: FastAPI app for web dashboard (not yet created) |

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
3. **Extension popup needs server running**: `cerebro serve` must be active before clicking "Cerebro this page".
4. **JSON round-trip loses `fetched_metadata`**: `Bookmark.to_dict()` omits `fetched_metadata`. If you need OG data persisted, use `from_dict()` with the full dict or switch to SQLite.
5. **Server concurrent writes**: `server.py` reads entire JSON, appends one bookmark, rewrites. No file locking — concurrent POSTs may overwrite each other. SQLite migration will fix this.

## Extension Development
- **Load unpacked**: `chrome://extensions/` → Developer mode → Load unpacked → select `browser-extension/`
- **Permissions needed**: `activeTab`, `storage`, `contextMenus`, `alarms`, `host_permissions: http://localhost:8765/*`
- **Keyboard shortcut**: `Ctrl+Shift+C` (registered in manifest `commands`)
- **Settings page**: `options.html` — configure host/port via `chrome.storage.local`

## Docker (Planned)
- `docker run -p 8765:8765 -p 8080:8080 cerebro` for server + dashboard
- Dockerfile not yet created.
