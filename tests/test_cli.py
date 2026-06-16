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
