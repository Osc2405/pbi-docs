"""
Multi-file indexed output for large Power BI models.

Writes (always):
  index.json           — lightweight summary + file pointers
  tables/<Name>.json   — full detail per table (columns + measures + DAX)
  relationships.json   — all relationships

With --index-format toon, the tabular arrays in tables/*.json and
relationships.json use TOON (Token-Oriented Object Notation) for
~30-60% token reduction. DAX expressions, agent_context.json,
metadata.json, and model_context.jsonl are never converted to TOON.

With --index-format auto, each table independently gets TOON or JSON
based on its own size (see _should_use_toon) — measured empirically on
files_test/Supply Chain Sample.pbip: TOON loses against JSON below ~7
rows (columns + measures) and wins above it (docs/token_optimization_report.md
section 4). relationships.json always uses TOON in auto mode since
relationships are inherently uniform and typically not tiny.
"""

import json
import re
from pathlib import Path
from typing import List

from .toon_encoder import encode_toon
from .formatters import categorize_dax_complexity


# Field order definitions for TOON encoding
_COLUMN_TOON_FIELDS = ["name", "data_type", "category", "is_hidden", "source_column", "format_string"]
_REL_TOON_FIELDS = ["from_table", "from_column", "to_table", "to_column",
                    "cardinality", "cross_filtering", "is_active"]
_MEASURE_FLAT_TOON_FIELDS = ["name", "category", "complexity", "is_hidden",
                              "format_string", "display_folder"]

# Empirical TOON/JSON crossover for --index-format auto, measured on
# files_test/Supply Chain Sample.pbip (docs/token_optimization_report.md section 4):
# 5 rows (columns+measures) still loses to JSON (+6.6% bytes), 7 rows already wins
# (-4.2%). No real data point at exactly 6, so 7 is the conservative cutoff.
_AUTO_TOON_MIN_ROWS = 7


def _should_use_toon(table: dict) -> bool:
    """Per-table auto-selection for --index-format auto: TOON only pays off
    once a table has enough columns+measures to amortize the {__toon,
    __fields, __rows} wrapper overhead."""
    rows = len(table.get("columns", [])) + len(table.get("measures", []))
    return rows >= _AUTO_TOON_MIN_ROWS


def _safe_filename(name: str) -> str:
    """Sanitize a table name for use as a filesystem filename."""
    return re.sub(r'[\\/:*?"<>|]', "_", name)


def _table_categories(table: dict) -> List[str]:
    """Collect unique measure categories present in a table."""
    seen = set()
    for m in table.get("measures", []):
        cat = m.get("category", "")
        if cat and cat != "other":
            seen.add(cat)
    return sorted(seen)


# ---------------------------------------------------------------------------
# JSON table/relationship builders (default format)
# ---------------------------------------------------------------------------

def _table_entry_json(t: dict) -> dict:
    return {
        "name": t["name"],
        "is_hidden": t.get("is_hidden", False),
        "is_technical": t.get("is_technical", False),
        "columns": t.get("columns", []),
        "measures": t.get("measures", []),
    }


# ---------------------------------------------------------------------------
# TOON table/relationship builders
# ---------------------------------------------------------------------------

def _flat_measure(m: dict) -> dict:
    """Build a flat measure record suitable for TOON encoding."""
    return {
        "name": m.get("name", ""),
        "category": m.get("category", "other"),
        "complexity": categorize_dax_complexity(m.get("expression", "")),
        "is_hidden": m.get("is_hidden", False),
        "format_string": m.get("format_string", ""),
        "display_folder": m.get("display_folder", ""),
    }


def _table_entry_toon(t: dict) -> dict:
    """Build a table entry where tabular arrays are TOON-encoded."""
    measures = t.get("measures", [])
    return {
        "name": t["name"],
        "is_hidden": t.get("is_hidden", False),
        "is_technical": t.get("is_technical", False),
        "columns": encode_toon(t.get("columns", []), _COLUMN_TOON_FIELDS),
        "measures_flat": encode_toon(
            [_flat_measure(m) for m in measures],
            _MEASURE_FLAT_TOON_FIELDS,
        ),
        "measures_dax": [
            {"name": m.get("name", ""), "formatted_expression": m.get("formatted_expression", "")}
            for m in measures
        ],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_index(cleaned_metadata: dict, source_format: str,
                index_format: str = "json") -> dict:
    """
    Build the index.json dict from cleaned_metadata.

    Args:
        cleaned_metadata: Output of processor.process_schema()
        source_format: 'pbit' or 'pbip'
        index_format: 'json' (default), 'toon', or 'auto' (per-table)

    Returns:
        dict ready to serialise as index.json
    """
    table_entries = []
    for t in cleaned_metadata.get("tables", []):
        name = t["name"]
        if index_format == "auto":
            table_format = "toon" if _should_use_toon(t) else "json"
        else:
            table_format = index_format
        table_entries.append({
            "name": name,
            "is_hidden": t.get("is_hidden", False),
            "is_technical": t.get("is_technical", False),
            "column_count": len(t.get("columns", [])),
            "measure_count": len(t.get("measures", [])),
            "categories": _table_categories(t),
            "format": table_format,
            "path": f"tables/{_safe_filename(name)}.json",
        })

    return {
        "version": "1",
        "model_name": cleaned_metadata.get("file_name", ""),
        "extraction_date": cleaned_metadata.get("extraction_date", ""),
        "compatibility_level": str(cleaned_metadata.get("compatibility_level", "")),
        "source_format": source_format,
        "index_format": index_format,
        "summary": cleaned_metadata.get("summary", {}),
        "tables": table_entries,
        "files": {
            "metadata": "metadata.json",
            "documentation": "model_documentation.md",
            "agent_context": "agent_context.json",
            "model_context": "model_context.jsonl",
            "relationships": "relationships.json",
        },
    }


def write_indexed_output(
    cleaned_metadata: dict,
    output_dir: Path,
    source_format: str,
    index_format: str = "json",
) -> None:
    """
    Write index.json, tables/<Name>.json, and relationships.json.
    Does not touch existing files (metadata.json, agent_context.json, etc.).

    Args:
        cleaned_metadata: Output of processor.process_schema()
        output_dir: Directory where the other output files already live
        source_format: 'pbit' or 'pbip'
        index_format: 'json' (full arrays, default), 'toon' (compact encoding
                      for column/relationship/flat-measure arrays), or 'auto'
                      (per-table: TOON only for tables large enough to benefit,
                      see _should_use_toon; relationships.json always uses TOON
                      in auto mode since relationships are inherently uniform)
    """
    is_auto = index_format == "auto"
    use_toon = index_format == "toon" or is_auto

    tables_dir = output_dir / "tables"
    tables_dir.mkdir(exist_ok=True)

    # --- relationships.json ------------------------------------------------
    relationships = cleaned_metadata.get("relationships", [])
    rels_data = (encode_toon(relationships, _REL_TOON_FIELDS)
                 if use_toon else relationships)
    rels_path = output_dir / "relationships.json"
    with open(rels_path, "w", encoding="utf-8") as f:
        json.dump(rels_data, f, indent=2, ensure_ascii=False)

    # --- tables/<Name>.json ------------------------------------------------
    for t in cleaned_metadata.get("tables", []):
        table_use_toon = _should_use_toon(t) if is_auto else use_toon
        table_entry = (_table_entry_toon(t) if table_use_toon
                       else _table_entry_json(t))
        fname = _safe_filename(t["name"]) + ".json"
        with open(tables_dir / fname, "w", encoding="utf-8") as f:
            json.dump(table_entry, f, indent=2, ensure_ascii=False)

    # --- index.json --------------------------------------------------------
    index = build_index(cleaned_metadata, source_format, index_format)
    with open(output_dir / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
