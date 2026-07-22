"""Tests for pbi_extractor.diff — content-aware comparison of two cleaned_metadata dicts."""

from pbi_extractor.diff import diff_models


def _measure(name, expression="SUM(Sales[Amount])", format_string="$#,0",
             is_hidden=False, display_folder="", category="revenue"):
    return {
        "name": name,
        "expression": expression,
        "formatted_expression": expression,
        "format_string": format_string,
        "is_hidden": is_hidden,
        "display_folder": display_folder,
        "category": category,
    }


def _column(name, data_type="string", format_string="", is_hidden=False,
            source_column=None, category="other"):
    return {
        "name": name,
        "data_type": data_type,
        "format_string": format_string,
        "is_hidden": is_hidden,
        "source_column": source_column or name,
        "category": category,
    }


def _relationship(from_table, from_column, to_table, to_column,
                   cardinality="many:one", cross_filtering="OneDirection", is_active=True):
    return {
        "name": f"Rel_{from_table}_{to_table}",
        "from_table": from_table, "from_column": from_column,
        "to_table": to_table, "to_column": to_column,
        "cardinality": cardinality, "cross_filtering": cross_filtering,
        "is_active": is_active,
    }


def _meta(tables=None, relationships=None, file_name="model"):
    return {
        "file_name": file_name,
        "tables": tables or [],
        "relationships": relationships or [],
    }


def _table(name, columns=None, measures=None):
    return {"name": name, "columns": columns or [], "measures": measures or []}


# ---------------------------------------------------------------------------
# Round-trip: no changes → everything empty
# ---------------------------------------------------------------------------

def test_diff_identical_models_is_all_empty():
    meta = _meta(tables=[_table("Sales", columns=[_column("Amount")],
                                 measures=[_measure("Total Sales")])],
                 relationships=[_relationship("Sales", "DateKey", "Date", "Date")])
    diff = diff_models(meta, meta)
    for key in ("measures_added", "measures_removed", "measures_modified",
                "columns_added", "columns_removed", "columns_modified",
                "relationships_added", "relationships_removed", "relationships_modified"):
        assert diff[key] == [], f"{key} should be empty for identical models"


# ---------------------------------------------------------------------------
# Measures
# ---------------------------------------------------------------------------

def test_measures_added_and_removed():
    meta_a = _meta(tables=[_table("Sales", measures=[_measure("Total Sales")])])
    meta_b = _meta(tables=[_table("Sales", measures=[_measure("Avg Sales")])])
    diff = diff_models(meta_a, meta_b)
    assert diff["measures_added"] == [("Sales", "Avg Sales")]
    assert diff["measures_removed"] == [("Sales", "Total Sales")]
    assert diff["measures_modified"] == []


def test_measure_semantic_dax_change():
    meta_a = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", expression="SUM(Sales[Amount])")])])
    meta_b = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", expression="AVERAGE(Sales[Amount])")])])
    diff = diff_models(meta_a, meta_b)
    assert diff["measures_added"] == []
    assert diff["measures_removed"] == []
    assert len(diff["measures_modified"]) == 1
    change = diff["measures_modified"][0]
    assert change["table"] == "Sales"
    assert change["name"] == "Total Sales"
    assert change["changes"]["formatted_expression"]["dax_change"] == "semantic"


def test_measure_cosmetic_only_dax_change():
    meta_a = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", expression="SUM(Sales[Amount])")])])
    meta_b = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", expression="SUM(\n\tSales[Amount]\n)")])])
    diff = diff_models(meta_a, meta_b)
    assert len(diff["measures_modified"]) == 1
    assert diff["measures_modified"][0]["changes"]["formatted_expression"]["dax_change"] == "cosmetic"


def test_measure_format_string_and_display_folder_change():
    meta_a = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", format_string="$#,0", display_folder="")])])
    meta_b = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", format_string="0.00%", display_folder="KPIs")])])
    diff = diff_models(meta_a, meta_b)
    assert len(diff["measures_modified"]) == 1
    changes = diff["measures_modified"][0]["changes"]
    assert changes["format_string"] == {"old": "$#,0", "new": "0.00%"}
    assert changes["display_folder"] == {"old": "", "new": "KPIs"}
    assert "formatted_expression" not in changes


def test_measure_is_hidden_change():
    meta_a = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", is_hidden=False)])])
    meta_b = _meta(tables=[_table("Sales", measures=[_measure("Total Sales", is_hidden=True)])])
    diff = diff_models(meta_a, meta_b)
    assert diff["measures_modified"][0]["changes"]["is_hidden"] == {"old": False, "new": True}


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def test_columns_added_and_removed():
    meta_a = _meta(tables=[_table("Sales", columns=[_column("Amount")])])
    meta_b = _meta(tables=[_table("Sales", columns=[_column("Quantity")])])
    diff = diff_models(meta_a, meta_b)
    assert diff["columns_added"] == [("Sales", "Quantity")]
    assert diff["columns_removed"] == [("Sales", "Amount")]
    assert diff["columns_modified"] == []


def test_column_data_type_change():
    meta_a = _meta(tables=[_table("Sales", columns=[_column("Amount", data_type="int64")])])
    meta_b = _meta(tables=[_table("Sales", columns=[_column("Amount", data_type="decimal")])])
    diff = diff_models(meta_a, meta_b)
    assert len(diff["columns_modified"]) == 1
    change = diff["columns_modified"][0]
    assert change["table"] == "Sales"
    assert change["name"] == "Amount"
    assert change["changes"]["data_type"] == {"old": "int64", "new": "decimal"}


# ---------------------------------------------------------------------------
# Relationships
# ---------------------------------------------------------------------------

def test_relationships_added_and_removed():
    meta_a = _meta(relationships=[_relationship("Sales", "DateKey", "Date", "Date")])
    meta_b = _meta(relationships=[_relationship("Sales", "StoreKey", "Store", "Store")])
    diff = diff_models(meta_a, meta_b)
    assert diff["relationships_added"] == [("Sales", "StoreKey", "Store", "Store")]
    assert diff["relationships_removed"] == [("Sales", "DateKey", "Date", "Date")]
    assert diff["relationships_modified"] == []


def test_relationship_cardinality_change_is_modified_not_add_remove():
    """Same connected columns, different cardinality — should be 'modified',
    not (add + remove), which is the whole point of keying identity on the
    connected columns rather than on every field."""
    meta_a = _meta(relationships=[_relationship("Sales", "DateKey", "Date", "Date", cardinality="many:one")])
    meta_b = _meta(relationships=[_relationship("Sales", "DateKey", "Date", "Date", cardinality="one:one")])
    diff = diff_models(meta_a, meta_b)
    assert diff["relationships_added"] == []
    assert diff["relationships_removed"] == []
    assert len(diff["relationships_modified"]) == 1
    change = diff["relationships_modified"][0]
    assert change["from_table"] == "Sales"
    assert change["changes"]["cardinality"] == {"old": "many:one", "new": "one:one"}


def test_relationship_is_active_change():
    meta_a = _meta(relationships=[_relationship("Sales", "DateKey", "Date", "Date", is_active=True)])
    meta_b = _meta(relationships=[_relationship("Sales", "DateKey", "Date", "Date", is_active=False)])
    diff = diff_models(meta_a, meta_b)
    assert diff["relationships_modified"][0]["changes"]["is_active"] == {"old": True, "new": False}
