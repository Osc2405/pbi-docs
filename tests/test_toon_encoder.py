"""Tests for TOON serialization (toon_encoder + indexed_output TOON mode)."""

import json
import pytest
from pathlib import Path

from pbi_extractor.toon_encoder import encode_toon, decode_toon
from pbi_extractor.indexed_output import build_index, write_indexed_output
from pbi_extractor.pbip_extractor import parse_pbip_model
from pbi_extractor.processor import process_schema

FIXTURES = Path(__file__).parent / "fixtures"
SM_DIR = FIXTURES / "minimal_pbip" / "my-model.SemanticModel"


@pytest.fixture
def metadata():
    schema = parse_pbip_model(str(SM_DIR))
    return process_schema(schema, "my-model")


# ---------------------------------------------------------------------------
# encode_toon / decode_toon
# ---------------------------------------------------------------------------

def test_toon_encode_structure():
    records = [
        {"name": "SalesAmount", "data_type": "decimal", "category": "metric", "is_hidden": False},
        {"name": "Date", "data_type": "dateTime", "category": "temporal", "is_hidden": False},
    ]
    fields = ["name", "data_type", "category", "is_hidden"]
    result = encode_toon(records, fields)

    assert result["__toon"] is True
    assert result["__fields"] == fields
    assert len(result["__rows"]) == 2
    assert result["__rows"][0] == ["SalesAmount", "decimal", "metric", False]
    assert result["__rows"][1] == ["Date", "dateTime", "temporal", False]


def test_toon_encode_columns(metadata):
    sales = next(t for t in metadata["tables"] if t["name"] == "Sales")
    fields = ["name", "data_type", "category", "is_hidden", "source_column", "format_string"]
    result = encode_toon(sales["columns"], fields)

    assert result["__toon"] is True
    assert result["__fields"] == fields
    assert len(result["__rows"]) == 3


def test_toon_encode_relationships(metadata):
    fields = ["from_table", "from_column", "to_table", "to_column",
              "cardinality", "cross_filtering", "is_active"]
    result = encode_toon(metadata["relationships"], fields)

    assert result["__toon"] is True
    assert len(result["__rows"]) == 2
    # Check one row
    active_row = next(r for r in result["__rows"] if r[-1] is True)  # is_active=True
    assert active_row[0] == "Sales"    # from_table
    assert active_row[2] == "Date"     # to_table


def test_toon_encode_empty_list():
    result = encode_toon([], ["name", "value"])
    assert result["__toon"] is True
    assert result["__rows"] == []


def test_toon_round_trip():
    records = [
        {"name": "Total Sales", "category": "revenue", "is_hidden": False, "format_string": "$#,0"},
        {"name": "YTD Sales", "category": "revenue", "is_hidden": False, "format_string": "$#,0"},
    ]
    fields = ["name", "category", "is_hidden", "format_string"]
    encoded = encode_toon(records, fields)
    decoded = decode_toon(encoded)

    assert len(decoded) == 2
    assert decoded[0] == records[0]
    assert decoded[1] == records[1]


def test_toon_round_trip_with_none_values():
    records = [{"name": "X", "value": None}]
    encoded = encode_toon(records, ["name", "value"])
    decoded = decode_toon(encoded)
    assert decoded[0]["value"] is None


def test_decode_toon_missing_field_returns_none():
    """Missing fields in a record produce None in the row."""
    records = [{"name": "X"}]  # "value" key absent
    encoded = encode_toon(records, ["name", "value"])
    assert encoded["__rows"][0] == ["X", None]
    decoded = decode_toon(encoded)
    assert decoded[0] == {"name": "X", "value": None}


# ---------------------------------------------------------------------------
# indexed_output TOON mode — relationships.json
# ---------------------------------------------------------------------------

def test_relationships_json_toon_structure(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "relationships.json", encoding="utf-8") as f:
        data = json.load(f)
    assert data["__toon"] is True
    assert "from_table" in data["__fields"]
    assert "is_active" in data["__fields"]
    assert len(data["__rows"]) == 2


def test_relationships_json_json_mode_is_list(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="json")
    with open(tmp_path / "relationships.json", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, list)


# ---------------------------------------------------------------------------
# indexed_output TOON mode — tables/<Name>.json
# ---------------------------------------------------------------------------

def test_table_json_toon_columns_encoded(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    columns = sales["columns"]
    assert columns["__toon"] is True
    assert "name" in columns["__fields"]
    assert len(columns["__rows"]) == 3


def test_table_json_toon_measures_flat_encoded(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    mf = sales["measures_flat"]
    assert mf["__toon"] is True
    assert "complexity" in mf["__fields"]
    assert len(mf["__rows"]) == 2


def test_table_json_toon_measures_dax_is_list(tmp_path, metadata):
    """measures_dax must remain a plain list, never TOON."""
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    dax = sales["measures_dax"]
    assert isinstance(dax, list)
    assert "formatted_expression" in dax[0]


def test_no_toon_in_json_mode_table(tmp_path, metadata):
    """In JSON mode, columns and measures are plain lists."""
    write_indexed_output(metadata, tmp_path, "pbip", index_format="json")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    assert isinstance(sales["columns"], list)
    assert isinstance(sales["measures"], list)
    assert "__toon" not in sales


def test_toon_table_has_no_measures_key(tmp_path, metadata):
    """TOON table uses measures_flat + measures_dax, not measures."""
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    assert "measures" not in sales
    assert "measures_flat" in sales
    assert "measures_dax" in sales


# ---------------------------------------------------------------------------
# index.json declares index_format
# ---------------------------------------------------------------------------

def test_index_json_declares_format_json(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="json")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    assert idx["index_format"] == "json"


def test_index_json_declares_format_toon(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    assert idx["index_format"] == "toon"


def test_build_index_includes_index_format(metadata):
    idx = build_index(metadata, "pbit", index_format="toon")
    assert idx["index_format"] == "toon"

    idx_json = build_index(metadata, "pbit", index_format="json")
    assert idx_json["index_format"] == "json"


# ---------------------------------------------------------------------------
# TOON must NOT appear in metadata.json / agent_context.json / jsonl
# (regression: write_indexed_output does not touch those files)
# ---------------------------------------------------------------------------

def test_no_toon_in_metadata_json(tmp_path, metadata):
    sentinel = tmp_path / "metadata.json"
    sentinel.write_text('{"sentinel": true}', encoding="utf-8")
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(sentinel, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"sentinel": True}


def test_no_toon_in_agent_context(tmp_path, metadata):
    sentinel = tmp_path / "agent_context.json"
    sentinel.write_text('{"sentinel": true}', encoding="utf-8")
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(sentinel, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"sentinel": True}


# ---------------------------------------------------------------------------
# complexity field is populated in measures_flat
# ---------------------------------------------------------------------------

def test_measures_flat_complexity_values(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    mf = sales["measures_flat"]
    complexity_idx = mf["__fields"].index("complexity")
    complexities = [row[complexity_idx] for row in mf["__rows"]]
    assert all(c in ("simple", "medium", "complex") for c in complexities)


# ---------------------------------------------------------------------------
# CLI flag --index-format toon is accepted
# ---------------------------------------------------------------------------

def test_cli_accepts_toon_flag():
    """Verify argparse accepts --index-format toon without error."""
    from pbi_extractor.cli import main
    # Just test that the flag is parsed without error (no input given, exits 1 cleanly)
    result = main(["--index-format", "toon"])
    # main() returns 1 when no --input given; that's fine — we only care it didn't crash on the flag
    assert result in (0, 1)


def test_cli_rejects_invalid_format():
    """--index-format with an unknown value should exit with error."""
    import subprocess, sys
    result = subprocess.run(
        [sys.executable, "-m", "pbi_extractor.cli", "--index-format", "xml"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).parent.parent),
    )
    assert result.returncode != 0
