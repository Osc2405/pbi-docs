"""Tests for pbi_extractor.pbip_extractor (TMDL / PBIP format)."""

import pytest
from pathlib import Path

from pbi_extractor.pbip_extractor import (
    find_semantic_model,
    parse_pbip_model,
    _parse_database_tmdl,
    _parse_table_tmdl_file,
    _parse_relationships_tmdl,
    _parse_table_column_ref,
    SemanticModelNotFoundError,
    TmdlParseError,
)
from pbi_extractor.processor import process_schema

FIXTURES = Path(__file__).parent / "fixtures"
SM_DIR = FIXTURES / "minimal_pbip" / "my-model.SemanticModel"
DEF_DIR = SM_DIR / "definition"
PROJECT_DIR = FIXTURES / "minimal_pbip"
PBIP_FILE = FIXTURES / "minimal_pbip" / "my-model.pbip"


# ---------------------------------------------------------------------------
# find_semantic_model
# ---------------------------------------------------------------------------

def test_find_semantic_model_from_sm_folder():
    result = find_semantic_model(str(SM_DIR))
    assert result == SM_DIR


def test_find_semantic_model_from_pbip_file():
    result = find_semantic_model(str(PBIP_FILE))
    assert result == SM_DIR


def test_find_semantic_model_from_project_folder():
    result = find_semantic_model(str(PROJECT_DIR))
    assert result == SM_DIR


def test_find_semantic_model_missing_raises():
    with pytest.raises(SemanticModelNotFoundError):
        find_semantic_model(str(FIXTURES / "nonexistent"))


def test_find_semantic_model_dir_without_sm_raises(tmp_path):
    with pytest.raises(SemanticModelNotFoundError):
        find_semantic_model(str(tmp_path))


# ---------------------------------------------------------------------------
# database.tmdl
# ---------------------------------------------------------------------------

def test_parse_database_compat_level():
    level = _parse_database_tmdl(DEF_DIR / "database.tmdl")
    assert level == 1604


def test_parse_database_default_when_missing(tmp_path):
    db = tmp_path / "database.tmdl"
    db.write_text("database empty\n", encoding="utf-8")
    assert _parse_database_tmdl(db) == 1604


# ---------------------------------------------------------------------------
# Table file parsing
# ---------------------------------------------------------------------------

def test_parse_table_name():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    assert table["name"] == "Sales"


def test_parse_table_hidden_flag():
    date_table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Date.tmdl")
    assert date_table["isHidden"] is True

    sales_table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    assert sales_table["isHidden"] is False


def test_parse_table_quoted_name():
    date_table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Date.tmdl")
    assert date_table["name"] == "Date"


def test_parse_columns_basic():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    cols = {c["name"]: c for c in table["columns"]}

    assert "SalesID" in cols
    assert cols["SalesID"]["dataType"] == "int64"
    assert cols["SalesID"]["sourceColumn"] == "SalesID"

    assert "SalesAmount" in cols
    assert cols["SalesAmount"]["dataType"] == "decimal"
    assert cols["SalesAmount"]["formatString"] == "$#,0.###;($#,0.###)"

    assert "DateKey" in cols
    assert cols["DateKey"]["dataType"] == "dateTime"


def test_parse_column_hidden_flag():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "_Measures.tmdl")
    cols = {c["name"]: c for c in table["columns"]}
    assert cols["MeasureID"]["isHidden"] is True


def test_parse_calculated_column_name_strips_expression(tmp_path):
    """`column 'Name' = <DAX>` must not leave the expression glued onto the column name."""
    tbl = tmp_path / "Calc.tmdl"
    tbl.write_text(
        "table Calc\n"
        "\tcolumn 'Manufactured (%)' = If('Calc'[X] <= 0.9, \">125%\", \"<75%\")\n"
        "\t\tisHidden\n"
        "\t\tlineageTag: abc-123\n",
        encoding="utf-8",
    )
    table = _parse_table_tmdl_file(tbl)
    assert len(table["columns"]) == 1
    assert table["columns"][0]["name"] == "Manufactured (%)"
    assert table["columns"][0]["isHidden"] is True


def test_parse_multiline_calculated_column_name_strips_expression(tmp_path):
    """`column 'Name' =` with the DAX body on following lines (multi-line form)."""
    tbl = tmp_path / "Calc.tmdl"
    tbl.write_text(
        "table Calc\n"
        "\tcolumn 'Manufactured (%)' =\n"
        "\t\tVAR x = 'Calc'[X]\n"
        "\t\tRETURN IF(x <= 0.9, \">125%\", \"<75%\")\n"
        "\tcolumn Plant\n"
        "\t\tdataType: string\n",
        encoding="utf-8",
    )
    table = _parse_table_tmdl_file(tbl)
    names = [c["name"] for c in table["columns"]]
    assert names == ["Manufactured (%)", "Plant"]


def test_parse_measures_count():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    assert len(table["measures"]) == 2


def test_parse_measure_single_line():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    measures = {m["name"]: m for m in table["measures"]}

    m = measures["Total Sales"]
    assert "SUM(Sales[SalesAmount])" in m["expression"]
    assert m["formatString"] == "$#,0"
    assert m["isHidden"] is False
    assert m["displayFolder"] == ""


def test_parse_measure_multiline_dax():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    measures = {m["name"]: m for m in table["measures"]}

    m = measures["YTD Sales"]
    expr = m["expression"]
    assert "CALCULATE" in expr
    assert "DATESYTD" in expr
    assert m["formatString"] == "$#,0"
    assert m["displayFolder"] == "Time Intelligence"


def test_parse_measure_complex_multiline_dax():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "_Measures.tmdl")
    measures = {m["name"]: m for m in table["measures"]}

    m = measures["Complex KPI"]
    expr = m["expression"]
    assert "VAR" in expr
    assert "DIVIDE" in expr
    assert m["formatString"] == "0.0%"
    assert m["displayFolder"] == "KPIs"


def test_parse_measure_backtick_fenced_dax(tmp_path):
    """`measure Name = ```<newline>...<newline>``` ` — Tabular Editor's fenced multi-line
    form. Must not leave the expression as the literal "```" fence marker."""
    tbl = tmp_path / "Calc.tmdl"
    tbl.write_text(
        "table Calc\n"
        "\tmeasure Value = ```\n"
        "\t\t\t\n"
        "\t\t\tIF (\n"
        "\t\t\t    HASONEVALUE ( 'Calc'[Code] ),\n"
        "\t\t\t    [Sales Amount]\n"
        "\t\t\t)\n"
        "\t\t\t```\n"
        "\t\tlineageTag: abc-123\n"
        "\tmeasure 'Next' = SUM(Calc[X])\n",
        encoding="utf-8",
    )
    table = _parse_table_tmdl_file(tbl)
    measures = {m["name"]: m for m in table["measures"]}

    assert len(table["measures"]) == 2
    m = measures["Value"]
    assert "```" not in m["expression"]
    assert "HASONEVALUE" in m["expression"]
    assert "[Sales Amount]" in m["expression"]
    assert measures["Next"]["expression"] == "SUM(Calc[X])"


def test_parse_partitions_counted():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Sales.tmdl")
    assert len(table["partitions"]) == 1


def test_no_measures_in_date_table():
    table = _parse_table_tmdl_file(DEF_DIR / "tables" / "Date.tmdl")
    assert table["measures"] == []


# ---------------------------------------------------------------------------
# Table.column reference parsing
# ---------------------------------------------------------------------------

def test_parse_table_column_ref_unquoted():
    assert _parse_table_column_ref("Sales.DateKey") == ("Sales", "DateKey")


def test_parse_table_column_ref_both_quoted():
    assert _parse_table_column_ref("'Date'.'Date'") == ("Date", "Date")


def test_parse_table_column_ref_unquoted_table_quoted_column():
    """Table unquoted but column has spaces and is quoted, e.g. Explanations.'Product ID'."""
    assert _parse_table_column_ref("Explanations.'Product ID'") == ("Explanations", "Product ID")


def test_parse_table_column_ref_quoted_table_unquoted_column():
    assert _parse_table_column_ref("'Backorder Percentage'.Month") == ("Backorder Percentage", "Month")


# ---------------------------------------------------------------------------
# Relationship parsing
# ---------------------------------------------------------------------------

def test_parse_relationships_count():
    rels = _parse_relationships_tmdl(DEF_DIR / "model.tmdl")
    assert len(rels) == 2


def test_parse_relationship_active():
    rels = {r["name"]: r for r in _parse_relationships_tmdl(DEF_DIR / "model.tmdl")}
    r = rels["Rel_Sales_Date"]
    assert r["fromTable"] == "Sales"
    assert r["fromColumn"] == "DateKey"
    assert r["toTable"] == "Date"
    assert r["toColumn"] == "Date"
    assert r["fromCardinality"] == "many"
    assert r["toCardinality"] == "one"
    assert r["isActive"] is True


def test_parse_relationship_inactive():
    rels = {r["name"]: r for r in _parse_relationships_tmdl(DEF_DIR / "model.tmdl")}
    r = rels["Rel_Sales_Measures"]
    assert r["isActive"] is False


def test_parse_relationship_quoted_name():
    """Date table name is quoted in model.tmdl as 'Date'."""
    rels = {r["name"]: r for r in _parse_relationships_tmdl(DEF_DIR / "model.tmdl")}
    assert rels["Rel_Sales_Date"]["toTable"] == "Date"


def test_parse_standalone_relationships_file(tmp_path):
    """Standalone relationships.tmdl declares 'relationship' at depth 0, not nested in model."""
    rel_file = tmp_path / "relationships.tmdl"
    rel_file.write_text(
        "relationship f1f4dec2-922f-4ec6-8dc1-49554a10a01c\n"
        "\tfromColumn: Explanations.'Product ID'\n"
        "\ttoColumn: Risk.'Product ID'\n",
        encoding="utf-8",
    )
    rels = _parse_relationships_tmdl(rel_file)
    assert len(rels) == 1
    assert rels[0]["fromTable"] == "Explanations"
    assert rels[0]["fromColumn"] == "Product ID"
    assert rels[0]["toTable"] == "Risk"
    assert rels[0]["toColumn"] == "Product ID"


# ---------------------------------------------------------------------------
# parse_pbip_model: top-level integration
# ---------------------------------------------------------------------------

def test_parse_pbip_model_raw_schema_shape():
    schema = parse_pbip_model(str(SM_DIR))
    assert "compatibilityLevel" in schema
    assert "model" in schema
    assert "tables" in schema["model"]
    assert "relationships" in schema["model"]


def test_parse_pbip_model_compat_level():
    schema = parse_pbip_model(str(SM_DIR))
    assert schema["compatibilityLevel"] == 1604


def test_parse_pbip_model_table_count():
    schema = parse_pbip_model(str(SM_DIR))
    assert len(schema["model"]["tables"]) == 3


def test_parse_pbip_model_relationship_count():
    schema = parse_pbip_model(str(SM_DIR))
    assert len(schema["model"]["relationships"]) == 2


def test_parse_pbip_model_from_project_folder():
    schema = parse_pbip_model(str(PROJECT_DIR))
    assert len(schema["model"]["tables"]) == 3


def test_parse_pbip_model_from_pbip_file():
    schema = parse_pbip_model(str(PBIP_FILE))
    assert len(schema["model"]["tables"]) == 3


# ---------------------------------------------------------------------------
# process_schema compatibility (parity)
# ---------------------------------------------------------------------------

def test_pbip_schema_compatible_with_processor():
    """parse_pbip_model output must pass through process_schema without errors."""
    schema = parse_pbip_model(str(SM_DIR))
    metadata = process_schema(schema, "my-model")

    assert metadata["summary"]["total_tables"] == 3
    assert metadata["summary"]["total_relationships"] == 2

    table_names = {t["name"] for t in metadata["tables"]}
    assert "Sales" in table_names
    assert "Date" in table_names
    assert "_Measures" in table_names


def test_pbip_parity_table_structure():
    """Cleaned metadata from PBIP matches expected structure."""
    schema = parse_pbip_model(str(SM_DIR))
    metadata = process_schema(schema, "my-model")

    tables = {t["name"]: t for t in metadata["tables"]}

    sales = tables["Sales"]
    assert len(sales["columns"]) == 3
    assert len(sales["measures"]) == 2
    assert sales["is_hidden"] is False
    assert sales["is_technical"] is False

    date = tables["Date"]
    assert len(date["columns"]) == 3
    assert date["is_hidden"] is True

    measures_table = tables["_Measures"]
    assert measures_table["is_hidden"] is True
    # _Measures is hidden but not "technical" per categorizer (no LocalDateTable_/etc prefix)
    assert measures_table["is_technical"] is False


def test_pbip_parity_relationships():
    schema = parse_pbip_model(str(SM_DIR))
    metadata = process_schema(schema, "my-model")

    rels = {r["name"]: r for r in metadata["relationships"]}
    assert "Rel_Sales_Date" in rels
    assert rels["Rel_Sales_Date"]["is_active"] is True
    assert rels["Rel_Sales_Measures"]["is_active"] is False


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_error_missing_semantic_model(tmp_path):
    with pytest.raises(SemanticModelNotFoundError):
        parse_pbip_model(str(tmp_path / "does_not_exist"))


def test_error_mixed_tabs_spaces(tmp_path):
    """A table file with space-indented lines should not crash — parser degrades gracefully."""
    sm = tmp_path / "bad.SemanticModel"
    definition = sm / "definition"
    tables = definition / "tables"
    tables.mkdir(parents=True)
    (definition / "model.tmdl").write_text("model Model\n", encoding="utf-8")

    bad_table = tables / "Bad.tmdl"
    bad_table.write_text(
        "table Bad\n"
        "    column Name\n"        # spaces instead of tabs
        "        dataType: string\n",
        encoding="utf-8",
    )

    schema = parse_pbip_model(str(sm))
    bad = next(t for t in schema["model"]["tables"] if t["name"] == "Bad")
    # With spaces, _count_tabs returns 0 so the column won't be parsed,
    # but the function must not raise an exception.
    assert isinstance(bad, dict)
