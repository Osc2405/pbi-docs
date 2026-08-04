"""Tests for pbi_extractor.graph_export and the --export-graph CLI flag."""

import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from pbi_extractor.cli import process_file
from pbi_extractor.graph_export import build_graph, to_graphml

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.pbip"
REPO_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def json_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("graph_export_json")
    process_file(FIXTURE, out, index_format="json")
    return out / "my-model"


# ---------------------------------------------------------------------------
# build_graph
# ---------------------------------------------------------------------------

def test_build_graph_nodes_include_every_table(json_dir):
    graph = build_graph(json_dir)
    assert {n["id"] for n in graph["nodes"]} == {"Sales", "Date", "_Measures"}


def test_build_graph_node_fields(json_dir):
    graph = build_graph(json_dir)
    sales = next(n for n in graph["nodes"] if n["id"] == "Sales")
    assert sales["is_hidden"] is False
    assert sales["is_technical"] is False
    assert sales["column_count"] == 3
    assert sales["measure_count"] == 2
    assert isinstance(sales["categories"], list)


def test_build_graph_edges_match_relationships(json_dir):
    from pbi_extractor import resolver
    graph = build_graph(json_dir)
    rels = resolver.get_relationships(json_dir)
    assert len(graph["edges"]) == len(rels)
    edge = next(e for e in graph["edges"] if e["target"] == "Date")
    assert edge["source"] == "Sales"
    assert edge["from_column"] == "DateKey"
    assert edge["to_column"] == "Date"
    assert edge["cardinality"] == "many:one"


# ---------------------------------------------------------------------------
# to_graphml
# ---------------------------------------------------------------------------

def test_to_graphml_is_well_formed_xml(json_dir):
    graph = build_graph(json_dir)
    xml_text = to_graphml(graph)
    root = ET.fromstring(xml_text)  # raises if malformed
    assert root.tag.endswith("graphml")


def test_to_graphml_contains_all_nodes_and_edges(json_dir):
    graph = build_graph(json_dir)
    xml_text = to_graphml(graph)
    root = ET.fromstring(xml_text)
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    node_ids = {n.get("id") for n in root.findall(".//g:graph/g:node", ns)}
    edges = root.findall(".//g:graph/g:edge", ns)
    assert node_ids == {"Sales", "Date", "_Measures"}
    assert len(edges) == len(graph["edges"])


def test_to_graphml_flattens_categories_list_to_comma_string():
    graph = {
        "nodes": [{"id": "Sales", "is_hidden": False, "is_technical": False,
                   "categories": ["revenue", "cost"], "column_count": 1, "measure_count": 1}],
        "edges": [],
    }
    xml_text = to_graphml(graph)
    assert "revenue,cost" in xml_text


def test_to_graphml_escapes_special_characters():
    graph = {
        "nodes": [{"id": "A & B", "is_hidden": False, "is_technical": False,
                   "categories": [], "column_count": 0, "measure_count": 0}],
        "edges": [],
    }
    xml_text = to_graphml(graph)
    root = ET.fromstring(xml_text)  # would raise on unescaped '&'
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    node = root.find(".//g:graph/g:node", ns)
    assert node.get("id") == "A & B"


# ---------------------------------------------------------------------------
# CLI --export-graph (real subprocess, mirrors tests/test_resolver.py's
# _run_cli helper for --query)
# ---------------------------------------------------------------------------

def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "pbi_extractor.cli", *args],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def test_cli_export_graph_default_json(json_dir):
    result = _run_cli("--query", str(json_dir), "--export-graph")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == build_graph(json_dir)


def test_cli_export_graph_graphml(json_dir):
    result = _run_cli("--query", str(json_dir), "--export-graph", "graphml")
    assert result.returncode == 0, result.stderr
    root = ET.fromstring(result.stdout)
    assert root.tag.endswith("graphml")


def test_cli_export_graph_invalid_format_rejected(json_dir):
    result = _run_cli("--query", str(json_dir), "--export-graph", "yaml")
    assert result.returncode != 0
