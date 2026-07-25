"""Behavior-lock regression tests for GEXF export via CLI commands.

Tests pin current behavior of `cerebro tag-graph` and `cerebro crosslinks
--export-format gexf` so that slop-removal refactoring does not change output.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from click.testing import CliRunner

from cerebro.cli import cli


def test_tag_graph_produces_valid_gexf(tmp_path: Path) -> None:
    """cerebro tag-graph on small JSON produces valid GEXF XML.

    Verifies:
    - <gexf> root element with xmlns and version
    - <graph> with defaultedgetype="undirected"
    - <nodes> and <edges> with count attributes
    - Nodes are tags, edges have weight
    """
    input_file = tmp_path / "bookmarks.json"
    input_file.write_text(
        json.dumps(
            [
                {"id": "a", "url": "https://a.com", "title": "A", "tags": ["python", "ml"]},
                {"id": "b", "url": "https://b.com", "title": "B", "tags": ["python", "rust"]},
                {"id": "c", "url": "https://c.com", "title": "C", "tags": ["ml", "rust"]},
            ]
        )
    )
    output_file = tmp_path / "graph.gexf"

    runner = CliRunner()
    result = runner.invoke(cli, ["tag-graph", str(input_file), "-o", str(output_file)])

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert output_file.exists(), "GEXF output file not created"

    text = output_file.read_text()

    # Root element
    assert "<gexf" in text
    assert 'xmlns="http://www.gexf.net/1.2draft"' in text
    assert 'version="1.2"' in text

    # Graph element with correct defaultedgetype
    assert 'defaultedgetype="undirected"' in text

    # Nodes with count attribute
    assert '<nodes count="3"' in text
    assert '<node id="ml" label="ml" />' in text
    assert '<node id="python" label="python" />' in text
    assert '<node id="rust" label="rust" />' in text

    # Edges with count attribute and weight
    assert '<edges count="3"' in text
    assert '<edge source="ml" target="python" weight="1" />' in text
    assert '<edge source="ml" target="rust" weight="1" />' in text
    assert '<edge source="python" target="rust" weight="1" />' in text


def test_crosslinks_gexf_produces_valid_xml(tmp_path: Path) -> None:
    """cerebro crosslinks --export-format gexf produces valid GEXF XML.

    Verifies:
    - <gexf> root element with xmlns and version
    - <graph> with defaultedgetype="directed"
    - <nodes> and <edges> with count attributes
    - Nodes are bookmark IDs with title labels
    - Edges are directed (source -> target), no weight
    """
    input_file = tmp_path / "bookmarks.json"
    input_file.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "url": "https://example.com/1",
                    "title": "Page One",
                    "domain": "example.com",
                    "tags": ["python", "ml"],
                    "category_breadcrumbs": ["Programming", "Python"],
                    "description": "A page about https://example.com/2",
                },
                {
                    "id": "b",
                    "url": "https://example.com/2",
                    "title": "Page Two",
                    "domain": "example.com",
                    "tags": ["python", "ml", "rust"],
                    "category_breadcrumbs": ["Programming", "Python"],
                    "description": "",
                },
            ]
        )
    )
    output_file = tmp_path / "crosslinked.json"

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "crosslinks",
            str(input_file),
            "-o",
            str(output_file),
            "-f",
            "gexf",
        ],
    )

    assert result.exit_code == 0, f"CLI failed: {result.output}"

    # JSON output always written (to_dict() does not include related_ids)
    assert output_file.exists(), "JSON output file not created"
    data = json.loads(output_file.read_text())
    assert len(data) == 2, "Expected 2 bookmarks in JSON output"

    # GEXF written alongside JSON
    gexf_file = output_file.with_suffix(".gexf")
    assert gexf_file.exists(), "GEXF output file not created"

    text = gexf_file.read_text()

    # Root element
    assert "<gexf" in text
    assert 'xmlns="http://www.gexf.net/1.2draft"' in text
    assert 'version="1.2"' in text

    # Graph element with correct defaultedgetype
    assert 'defaultedgetype="directed"' in text

    # Nodes with count attribute
    assert '<nodes count="2"' in text
    assert '<node id="a" label="Page One" />' in text
    assert '<node id="b" label="Page Two" />' in text

    # Edges with count attribute, no weight
    assert '<edges count="2"' in text
    assert '<edge source="a" target="b" />' in text
    assert '<edge source="b" target="a" />' in text
    assert "weight" not in text, "Crosslinks GEXF should not have edge weights"


def test_tag_graph_escapes_xml(tmp_path: Path) -> None:
    """tag-graph must escape XML special chars in node labels and edge endpoints."""
    # Arrange - tags with XML special characters
    input_file = tmp_path / "bookmarks.json"
    input_file.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "url": "https://a.com",
                    "title": "A",
                    "tags": ["a&b", "c<d"],
                },
                {
                    "id": "b",
                    "url": "https://b.com",
                    "title": "B",
                    "tags": ["a&b", "c<d"],
                },
            ]
        )
    )
    output_file = tmp_path / "graph.gexf"

    # Act
    runner = CliRunner()
    result = runner.invoke(cli, ["tag-graph", str(input_file), "-o", str(output_file)])

    # Assert
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert output_file.exists(), "GEXF output file not created"
    text = output_file.read_text()

    # Escaped forms present
    assert "&amp;" in text, "Ampersand not escaped in GEXF"
    assert "&lt;" in text, "Less-than not escaped in GEXF"

    # Raw special chars must NOT appear inside attribute values
    assert 'label="a&b"' not in text, "Raw unescaped & in label attribute"
    assert 'label="c<d"' not in text, "Raw unescaped < in label attribute"
    assert 'source="a&b"' not in text, "Raw unescaped & in source attribute"
    assert 'target="c<d"' not in text, "Raw unescaped < in target attribute"


# ---------------------------------------------------------------------------
# cli_admin commands — migrate-db, db-status, serve, dashboard, git-push
# ---------------------------------------------------------------------------


def test_migrate_db_command(tmp_path: Path) -> None:
    """cerebro migrate-db creates the SQLite database and reports ready."""
    config = tmp_path / ".cerebro.toml"
    config.write_text(f'''
[database]
path = "{tmp_path / "cerebro.db"}"
''')
    runner = CliRunner()
    result = runner.invoke(cli, ["--config", str(config), "migrate-db"])
    assert result.exit_code == 0, f"migrate-db failed: {result.output}"
    assert "Database ready" in result.output
    assert "Existing bookmarks: 0" in result.output


def test_db_status_command(tmp_path: Path) -> None:
    """cerebro db-status prints bookmark and dead-link counts."""
    config = tmp_path / ".cerebro.toml"
    config.write_text(f'''
[database]
path = "{tmp_path / "cerebro.db"}"
''')
    runner = CliRunner()
    # Run migrate first so tables exist
    runner.invoke(cli, ["--config", str(config), "migrate-db"])
    result = runner.invoke(cli, ["--config", str(config), "db-status"])
    assert result.exit_code == 0, f"db-status failed: {result.output}"
    assert "Total bookmarks:" in result.output
    assert "Dead links:" in result.output


def test_serve_command_calls_run_server(tmp_path: Path) -> None:
    """cerebro serve defers to run_server with config host/port."""
    from unittest.mock import patch

    config = tmp_path / ".cerebro.toml"
    config.write_text("""
[server]
host = "127.0.0.1"
port = 8765
""")
    runner = CliRunner()
    with patch("cerebro.cli.run_server") as mock_run:
        result = runner.invoke(cli, ["--config", str(config), "serve"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs.get("host") == "127.0.0.1"
        assert kwargs.get("port") == 8765


def test_dashboard_command_calls_run_dashboard(tmp_path: Path) -> None:
    """cerebro dashboard defers to run_dashboard with config host/port."""
    from unittest.mock import patch

    config = tmp_path / ".cerebro.toml"
    config.write_text("""
[dashboard]
host = "127.0.0.1"
port = 8080
""")
    runner = CliRunner()
    with patch("cerebro.cli.run_dashboard") as mock_run:
        result = runner.invoke(cli, ["--config", str(config), "dashboard"])
        assert result.exit_code == 0, result.output
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        assert kwargs.get("host") == "127.0.0.1"
        assert kwargs.get("port") == 8080


def test_git_push_not_a_repo(tmp_path: Path) -> None:
    """cerebro git-push on a directory without .git warns and returns."""
    vault = tmp_path / "vault"
    vault.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["git-push", "--vault-dir", str(vault)])
    assert result.exit_code == 0, result.output
    assert "is not a git repository" in result.output


# ---------------------------------------------------------------------------
# cli.py single-stage commands — parse, classify, dedup, search, config
# ---------------------------------------------------------------------------


def test_parse_command(tmp_path: Path) -> None:
    """cerebro parse writes a JSON file of parsed bookmarks."""
    repo_root = Path(__file__).resolve().parents[1]
    sample_html = repo_root / ".github" / "testdata" / "sample.html"
    output = tmp_path / "raw.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["parse", str(sample_html), "--output", str(output)])
    assert result.exit_code == 0, f"parse failed: {result.output}"
    assert output.exists(), "parse output file not created"
    data = json.loads(output.read_text())
    assert len(data) == 16, f"expected 16 bookmarks, got {len(data)}"
    assert "Parsed" in result.output


def test_classify_command(tmp_path: Path) -> None:
    """cerebro classify tags bookmarks using taxonomy.yaml."""
    repo_root = Path(__file__).resolve().parents[1]
    taxonomy = repo_root / "taxonomy.yaml"
    input_file = tmp_path / "raw.json"
    # Minimal valid bookmark dict
    input_file.write_text(
        json.dumps(
            [{"id": "a", "url": "https://github.com/torvalds/linux", "title": "Linux kernel"}]
        )
    )
    output = tmp_path / "classified.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "classify",
            str(input_file),
            "--taxonomy",
            str(taxonomy),
            "--output",
            str(output),
            "--no-ml",
        ],
    )
    assert result.exit_code == 0, f"classify failed: {result.output}"
    assert output.exists(), "classify output file not created"
    assert "Classified" in result.output


def test_dedup_command(tmp_path: Path) -> None:
    """cerebro dedup marks duplicates and reports group count."""
    input_file = tmp_path / "bookmarks.json"
    input_file.write_text(
        json.dumps(
            [
                {"id": "a", "url": "https://example.com", "title": "Example"},
                {"id": "b", "url": "https://example.com", "title": "Example"},
            ]
        )
    )
    output = tmp_path / "deduped.json"
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["dedup", str(input_file), "--mode", "normalized", "--output", str(output)],
    )
    assert result.exit_code == 0, f"dedup failed: {result.output}"
    assert output.exists(), "dedup output file not created"
    assert "Deduped" in result.output


def test_search_command(tmp_path: Path) -> None:
    """cerebro search runs TF-IDF search over an enriched bookmarks file."""
    input_file = tmp_path / "enriched.json"
    input_file.write_text(
        json.dumps(
            [
                {
                    "id": "a",
                    "url": "https://a.com",
                    "title": "Python tutorial",
                    "tags": ["python"],
                    "category_breadcrumbs": ["Programming", "Python"],
                },
                {
                    "id": "b",
                    "url": "https://b.com",
                    "title": "Rust guide",
                    "tags": ["rust"],
                    "category_breadcrumbs": ["Programming", "Rust"],
                },
            ]
        )
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["search", str(input_file), "python", "--top-k", "5"])
    assert result.exit_code == 0, f"search failed: {result.output}"
    assert "Python tutorial" in result.output


def test_search_command_no_results(tmp_path: Path) -> None:
    """cerebro search with no matches prints the no-results message."""
    input_file = tmp_path / "enriched.json"
    input_file.write_text(
        json.dumps(
            [
                {"id": "a", "url": "https://a.com", "title": "Python tutorial", "tags": ["python"]},
                {"id": "b", "url": "https://b.com", "title": "Rust guide", "tags": ["rust"]},
            ]
        )
    )
    runner = CliRunner()
    result = runner.invoke(cli, ["search", str(input_file), "zzznomatch", "--min-score", "0.99"])
    assert result.exit_code == 0, f"search failed: {result.output}"
    assert "No results found." in result.output


def test_config_command(tmp_path: Path) -> None:
    """cerebro config prints loaded settings sections."""
    config = tmp_path / ".cerebro.toml"
    config.write_text(f"""
[server]
host = "127.0.0.1"
port = 8765
[database]
path = "{tmp_path / "cerebro.db"}"
""")
    runner = CliRunner()
    result = runner.invoke(cli, ["--config", str(config), "config"])
    assert result.exit_code == 0, f"config failed: {result.output}"
    assert "database.path" in result.output
    assert "server.host" in result.output
    assert "dashboard.host" in result.output
    assert "fetcher.timeout" in result.output
    assert "ml.enable_classifier" in result.output
