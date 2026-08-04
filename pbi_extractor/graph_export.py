"""
Project a processed model's tables/relationships to a generic graph shape,
consumable by external graph visualization tools (Gephi, yEd, etc.) — not a
query engine, and not exposed as an MCP tool (an agent that already has
list_tables/get_relationships can reconstruct the same information; a
GraphML/XML blob isn't useful tool-call context). See CLAUDE.md section 4.

Two output formats from the same {"nodes": [...], "edges": [...]} shape:
  - JSON: node/edge lists, printed as-is via --export-graph (default).
  - GraphML: XML, printed via --export-graph graphml.
"""

from pathlib import Path
from typing import List
from xml.sax.saxutils import escape, quoteattr

from . import resolver


def build_graph(model_dir: Path) -> dict:
    """
    Build {"nodes": [...], "edges": [...]} from an already-processed model
    directory, reusing resolver.list_tables()/get_relationships() — no new
    extraction.

    Every table is a node, including isolated ones (no relationships) —
    unlike documentation.generate_mermaid_er(), which omits them for human
    readability, here the consumer is an external tool that may want to see
    disconnected tables too.
    """
    tables = resolver.list_tables(model_dir)
    relationships = resolver.get_relationships(model_dir)

    nodes = [
        {
            "id": t["name"],
            "is_hidden": t["is_hidden"],
            "is_technical": t["is_technical"],
            "categories": t.get("categories", []),
            "column_count": t["column_count"],
            "measure_count": t["measure_count"],
        }
        for t in tables
    ]
    edges = [
        {
            "source": r["from_table"],
            "target": r["to_table"],
            "from_column": r["from_column"],
            "to_column": r["to_column"],
            "cardinality": r["cardinality"],
            "cross_filtering": r["cross_filtering"],
            "is_active": r["is_active"],
        }
        for r in relationships
    ]
    return {"nodes": nodes, "edges": edges}


_NODE_KEYS = [
    ("is_hidden", "boolean"),
    ("is_technical", "boolean"),
    ("categories", "string"),  # flattened: GraphML attr.type has no list/array
    ("column_count", "int"),
    ("measure_count", "int"),
]
_EDGE_KEYS = [
    ("from_column", "string"),
    ("to_column", "string"),
    ("cardinality", "string"),
    ("cross_filtering", "string"),
    ("is_active", "boolean"),
]


def _graphml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return escape(",".join(value))
    return escape(str(value))


def _data_lines(record: dict, keys: List[tuple], prefix: str, indent: str) -> List[str]:
    lines = []
    for key, _ in keys:
        lines.append(f'{indent}<data key="{prefix}_{key}">{_graphml_value(record[key])}</data>')
    return lines


def to_graphml(graph: dict) -> str:
    """
    Render a build_graph() result as GraphML XML (stdlib only — no lxml/etree
    dependency needed for output this simple, just string building with
    xml.sax.saxutils.escape/quoteattr for safe text/attribute values, since
    table/column names can contain '&'/'<'/'>').

    `categories` (a list in the JSON shape) has no GraphML scalar attr.type,
    so it's flattened to a comma-joined string here — a documented format
    difference, not a bug. edgedefault="directed": from_table -> to_table,
    same direction already used throughout processor.py/diff.py.
    """
    lines = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
    ]
    for key, attr_type in _NODE_KEYS:
        lines.append(f'  <key id="n_{key}" for="node" attr.name="{key}" attr.type="{attr_type}"/>')
    for key, attr_type in _EDGE_KEYS:
        lines.append(f'  <key id="e_{key}" for="edge" attr.name="{key}" attr.type="{attr_type}"/>')
    lines.append('  <graph id="G" edgedefault="directed">')

    for node in graph["nodes"]:
        lines.append(f'    <node id={quoteattr(node["id"])}>')
        lines.extend(_data_lines(node, _NODE_KEYS, "n", "      "))
        lines.append("    </node>")

    for edge in graph["edges"]:
        lines.append(f'    <edge source={quoteattr(edge["source"])} target={quoteattr(edge["target"])}>')
        lines.extend(_data_lines(edge, _EDGE_KEYS, "e", "      "))
        lines.append("    </edge>")

    lines.append("  </graph>")
    lines.append("</graphml>")
    return "\n".join(lines)
