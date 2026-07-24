"""Tests for pbi_extractor.indexed_output (Fase C)."""

import json
import pytest
from pathlib import Path

from pbi_extractor.indexed_output import build_index, write_indexed_output, _should_use_toon
from pbi_extractor.pbip_extractor import parse_pbip_model
from pbi_extractor.processor import process_schema

FIXTURES = Path(__file__).parent / "fixtures"
SM_DIR = FIXTURES / "minimal_pbip" / "my-model.SemanticModel"


@pytest.fixture
def metadata():
    schema = parse_pbip_model(str(SM_DIR))
    return process_schema(schema, "my-model")


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------

def test_build_index_top_level_keys(metadata):
    idx = build_index(metadata, "pbip")
    for key in ("version", "model_name", "extraction_date", "compatibility_level",
                 "source_format", "summary", "tables", "files"):
        assert key in idx


def test_build_index_source_format(metadata):
    assert build_index(metadata, "pbip")["source_format"] == "pbip"
    assert build_index(metadata, "pbit")["source_format"] == "pbit"


def test_build_index_table_count(metadata):
    idx = build_index(metadata, "pbip")
    assert len(idx["tables"]) == 3


def test_build_index_table_entry_fields(metadata):
    idx = build_index(metadata, "pbip")
    entry = next(t for t in idx["tables"] if t["name"] == "Sales")
    assert entry["column_count"] == 3
    assert entry["measure_count"] == 2
    assert entry["is_hidden"] is False
    assert entry["path"] == "tables/Sales.json"
    assert entry["partition_count"] == 1


def test_build_index_partition_count_defaults_to_zero_when_missing():
    idx = build_index({"tables": [_table(5, 0)]}, "pbip")
    assert idx["tables"][0]["partition_count"] == 0


def test_build_index_hidden_table(metadata):
    idx = build_index(metadata, "pbip")
    date_entry = next(t for t in idx["tables"] if t["name"] == "Date")
    assert date_entry["is_hidden"] is True


def test_build_index_files_section(metadata):
    idx = build_index(metadata, "pbip")
    files = idx["files"]
    assert files["metadata"] == "metadata.json"
    assert files["documentation"] == "model_documentation.md"
    assert files["relationships"] == "relationships.json"


def test_build_index_summary_preserved(metadata):
    idx = build_index(metadata, "pbip")
    assert idx["summary"] == metadata["summary"]


# ---------------------------------------------------------------------------
# write_indexed_output
# ---------------------------------------------------------------------------

def test_write_creates_index_json(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    assert (tmp_path / "index.json").exists()


def test_write_creates_relationships_json(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    assert (tmp_path / "relationships.json").exists()


def test_write_creates_tables_directory(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    assert (tmp_path / "tables").is_dir()


def test_write_creates_one_file_per_table(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    table_files = list((tmp_path / "tables").glob("*.json"))
    assert len(table_files) == 3


def test_index_paths_reference_existing_files(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    for entry in idx["tables"]:
        assert (tmp_path / entry["path"]).exists(), f"Missing: {entry['path']}"


def test_table_json_content(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    assert sales["name"] == "Sales"
    assert len(sales["columns"]) == 3
    assert len(sales["measures"]) == 2
    assert "formatted_expression" in sales["measures"][0]
    assert sales["partition_count"] == 1


def test_table_toon_content_partition_count(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", index_format="toon")
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    assert sales["partition_count"] == 1
    assert isinstance(sales["partition_count"], int)


def test_index_json_table_entries_have_partition_count(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    for entry in idx["tables"]:
        assert "partition_count" in entry
        assert entry["partition_count"] >= 0


def test_relationships_json_content(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(tmp_path / "relationships.json", encoding="utf-8") as f:
        rels = json.load(f)
    assert len(rels) == 2
    names = {r["name"] for r in rels}
    assert "Rel_Sales_Date" in names


def test_no_regression_metadata_json(tmp_path, metadata):
    """write_indexed_output must not overwrite metadata.json."""
    sentinel = tmp_path / "metadata.json"
    sentinel.write_text('{"sentinel": true}', encoding="utf-8")
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(sentinel, encoding="utf-8") as f:
        data = json.load(f)
    assert data == {"sentinel": True}


def test_index_json_valid_json(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        data = json.load(f)
    assert isinstance(data, dict)


# ---------------------------------------------------------------------------
# Compact vs pretty JSON (default is compact — docs/scale_validation_report.md
# section 5.1: indent=2 alone accounted for a measured 44.3% size inflation
# at scale, on files meant for resolver.py/mcp_server.py/LLM consumption,
# not human reading)
# ---------------------------------------------------------------------------

_INDEXED_OUTPUT_FILES = ("index.json", "relationships.json",
                         Path("tables") / "Sales.json")


def test_default_output_is_compact(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip")
    for rel in _INDEXED_OUTPUT_FILES:
        raw = (tmp_path / rel).read_text(encoding="utf-8")
        assert "\n" not in raw, f"{rel} should be a single line by default"
        assert ": " not in raw and ", " not in raw, f"{rel} should have no spaces after separators"


def test_pretty_flag_restores_indentation(tmp_path, metadata):
    write_indexed_output(metadata, tmp_path, "pbip", pretty=True)
    for rel in _INDEXED_OUTPUT_FILES:
        raw = (tmp_path / rel).read_text(encoding="utf-8")
        assert "\n  " in raw, f"{rel} should be indented when pretty=True"


def test_compact_and_pretty_are_content_identical(tmp_path, metadata):
    compact_dir, pretty_dir = tmp_path / "compact", tmp_path / "pretty"
    compact_dir.mkdir()
    pretty_dir.mkdir()
    write_indexed_output(metadata, compact_dir, "pbip", pretty=False)
    write_indexed_output(metadata, pretty_dir, "pbip", pretty=True)
    for rel in _INDEXED_OUTPUT_FILES:
        with open(compact_dir / rel, encoding="utf-8") as f:
            compact_data = json.load(f)
        with open(pretty_dir / rel, encoding="utf-8") as f:
            pretty_data = json.load(f)
        assert compact_data == pretty_data, f"{rel} differs in content, not just whitespace"


# ---------------------------------------------------------------------------
# --index-format auto (per-table TOON/JSON selection)
# ---------------------------------------------------------------------------

def _table(n_columns, n_measures, name="T"):
    return {
        "name": name,
        "is_hidden": False,
        "is_technical": False,
        "columns": [{"name": f"c{i}"} for i in range(n_columns)],
        "measures": [{"name": f"m{i}"} for i in range(n_measures)],
    }


def test_should_use_toon_below_threshold():
    assert _should_use_toon(_table(5, 0)) is False   # 5 rows: measured loss (+6.6%)


def test_should_use_toon_at_threshold():
    assert _should_use_toon(_table(7, 0)) is True    # 7 rows: measured win (-4.2%)


def test_auto_format_small_tables_stay_json(tmp_path, metadata):
    """The minimal_pbip fixture's tables are all well under the TOON threshold."""
    write_indexed_output(metadata, tmp_path, "pbip", index_format="auto")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    assert idx["index_format"] == "auto"
    assert all(t["format"] == "json" for t in idx["tables"])
    with open(tmp_path / "tables" / "Sales.json", encoding="utf-8") as f:
        sales = json.load(f)
    assert "measures_flat" not in sales  # plain JSON shape, not TOON


def test_auto_format_large_table_gets_toon(tmp_path, metadata):
    """A synthetic 14-row table injected alongside the fixture's tables must
    get TOON under auto, while the fixture's small tables stay JSON."""
    big_table = _table(14, 0, name="BigTable")
    metadata_with_big = {**metadata, "tables": metadata["tables"] + [big_table]}
    write_indexed_output(metadata_with_big, tmp_path, "pbip", index_format="auto")
    with open(tmp_path / "index.json", encoding="utf-8") as f:
        idx = json.load(f)
    formats = {t["name"]: t["format"] for t in idx["tables"]}
    assert formats["BigTable"] == "toon"
    assert formats["Sales"] == "json"

    with open(tmp_path / "tables" / "BigTable.json", encoding="utf-8") as f:
        big = json.load(f)
    assert "measures_flat" in big  # TOON shape
