"""Tests for extractor.py (.pbit / TMSL extraction path).

No .pbit fixture existed anywhere in the repo before this file (see
Pruebas/auditoria_general_2026-07-24.md, P0 #1) — every case here builds its
own zip in tmp_path rather than committing a binary fixture, consistent with
the project's zero-external-fixture-when-avoidable style already used for
in-memory schema dicts elsewhere in the test suite.
"""

import json
import zipfile

import pytest

from pbi_extractor.extractor import (
    FileNotFoundError as PBITFileNotFoundError,
    SchemaNotFoundError,
    SchemaParseError,
    clean_json_text,
    parse_datamodel_schema,
    parse_json_with_fallback,
    validate_input_file,
    validate_schema_structure,
    validate_zip_structure,
)

VALID_SCHEMA = {
    "model": {
        "tables": [
            {
                "name": "Sales",
                "columns": [{"name": "ID", "dataType": "int64"}],
                "measures": [{"name": "Total", "expression": "SUM(Sales[ID])"}],
            }
        ],
        "relationships": [],
    }
}


def _make_pbit(path, files: dict) -> None:
    """Write a .pbit (zip) at `path` with the given {name: content} entries."""
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in files.items():
            zf.writestr(name, content)


# ---------------------------------------------------------------------------
# validate_input_file
# ---------------------------------------------------------------------------

def test_validate_input_file_missing(tmp_path):
    with pytest.raises(PBITFileNotFoundError, match="does not exist"):
        validate_input_file(str(tmp_path / "ghost.pbit"))


def test_validate_input_file_is_directory(tmp_path):
    d = tmp_path / "not_a_file.pbit"
    d.mkdir()
    with pytest.raises(PBITFileNotFoundError, match="not a file"):
        validate_input_file(str(d))


def test_validate_input_file_wrong_extension(tmp_path):
    f = tmp_path / "model.zip"
    f.write_bytes(b"data")
    with pytest.raises(PBITFileNotFoundError, match="Only .pbit files"):
        validate_input_file(str(f))


def test_validate_input_file_empty(tmp_path):
    f = tmp_path / "model.pbit"
    f.write_bytes(b"")
    with pytest.raises(PBITFileNotFoundError, match="empty"):
        validate_input_file(str(f))


def test_validate_input_file_valid(tmp_path):
    f = tmp_path / "model.pbit"
    f.write_bytes(b"data")
    assert validate_input_file(str(f)) == f


# ---------------------------------------------------------------------------
# validate_zip_structure
# ---------------------------------------------------------------------------

def test_validate_zip_structure_empty_zip(tmp_path):
    p = tmp_path / "empty.pbit"
    with zipfile.ZipFile(p, "w"):
        pass
    with zipfile.ZipFile(p, "r") as zf:
        with pytest.raises(SchemaNotFoundError, match="empty or corrupted"):
            validate_zip_structure(zf)


def test_validate_zip_structure_no_model_file(tmp_path):
    p = tmp_path / "nomodel.pbit"
    _make_pbit(p, {"Report/Layout": "{}", "Version": "1.0"})
    with zipfile.ZipFile(p, "r") as zf:
        with pytest.raises(SchemaNotFoundError, match="DataModelSchema"):
            validate_zip_structure(zf)


def test_validate_zip_structure_finds_datamodelschema(tmp_path):
    p = tmp_path / "ok.pbit"
    _make_pbit(p, {"DataModelSchema": "{}"})
    with zipfile.ZipFile(p, "r") as zf:
        assert validate_zip_structure(zf) == ["DataModelSchema"]


# ---------------------------------------------------------------------------
# clean_json_text
# ---------------------------------------------------------------------------

def test_clean_json_text_removes_bom_and_nulls():
    assert clean_json_text("﻿{\x00}") == "{}"


def test_clean_json_text_removes_line_comments():
    text = '{\n  "a": 1, // comment\n  "b": 2\n}'
    cleaned = clean_json_text(text)
    assert json.loads(cleaned) == {"a": 1, "b": 2}


def test_clean_json_text_removes_block_comments():
    text = '{ /* block comment */ "a": 1 }'
    cleaned = clean_json_text(text)
    assert json.loads(cleaned) == {"a": 1}


def test_clean_json_text_removes_trailing_commas():
    text = '{"a": 1, "b": [1, 2, 3,],}'
    cleaned = clean_json_text(text)
    assert json.loads(cleaned) == {"a": 1, "b": [1, 2, 3]}


# ---------------------------------------------------------------------------
# parse_json_with_fallback
# ---------------------------------------------------------------------------

def test_parse_json_with_fallback_valid_utf8():
    raw = json.dumps({"a": 1}).encode("utf-8")
    assert parse_json_with_fallback(raw, "f.json") == {"a": 1}


def test_parse_json_with_fallback_valid_utf16():
    raw = json.dumps({"a": 1}).encode("utf-16")
    assert parse_json_with_fallback(raw, "f.json") == {"a": 1}


def test_parse_json_with_fallback_cleans_trailing_comma():
    raw = b'{"a": 1,}'
    assert parse_json_with_fallback(raw, "f.json") == {"a": 1}


def test_parse_json_with_fallback_unparseable_raises():
    raw = b"{not json at all"
    with pytest.raises(SchemaParseError, match="Error parsing JSON"):
        parse_json_with_fallback(raw, "f.json")


# ---------------------------------------------------------------------------
# validate_schema_structure
# ---------------------------------------------------------------------------

def test_validate_schema_structure_not_a_dict():
    with pytest.raises(SchemaParseError, match="must be a JSON object"):
        validate_schema_structure([1, 2, 3])


def test_validate_schema_structure_missing_model_key():
    with pytest.raises(SchemaParseError, match="'model' key"):
        validate_schema_structure({"foo": "bar"})


def test_validate_schema_structure_model_not_a_dict():
    with pytest.raises(SchemaParseError, match="'model' key must be an object"):
        validate_schema_structure({"model": "not a dict"})


def test_validate_schema_structure_missing_tables_and_relationships():
    with pytest.raises(SchemaParseError, match="required keys"):
        validate_schema_structure({"model": {}})


def test_validate_schema_structure_tables_not_a_list():
    with pytest.raises(SchemaParseError, match="'tables' key must be a list"):
        validate_schema_structure({"model": {"tables": {}, "relationships": []}})


def test_validate_schema_structure_relationships_not_a_list():
    with pytest.raises(SchemaParseError, match="'relationships' key must be a list"):
        validate_schema_structure({"model": {"tables": [], "relationships": {}}})


def test_validate_schema_structure_valid():
    validate_schema_structure(VALID_SCHEMA)  # must not raise


# ---------------------------------------------------------------------------
# parse_datamodel_schema (end-to-end over a real in-memory .pbit zip)
# ---------------------------------------------------------------------------

def test_parse_datamodel_schema_happy_path(tmp_path):
    p = tmp_path / "model.pbit"
    _make_pbit(p, {"DataModelSchema": json.dumps(VALID_SCHEMA)})
    schema = parse_datamodel_schema(str(p))
    assert schema == VALID_SCHEMA


def test_parse_datamodel_schema_corrupt_zip(tmp_path):
    p = tmp_path / "corrupt.pbit"
    p.write_bytes(b"this is not a zip file at all")
    with pytest.raises(PBITFileNotFoundError, match="not a valid ZIP"):
        parse_datamodel_schema(str(p))


def test_parse_datamodel_schema_missing_schema_file(tmp_path):
    p = tmp_path / "noschema.pbit"
    _make_pbit(p, {"Report/Layout": "{}"})
    with pytest.raises(SchemaNotFoundError):
        parse_datamodel_schema(str(p))


def test_parse_datamodel_schema_invalid_json(tmp_path):
    p = tmp_path / "badjson.pbit"
    _make_pbit(p, {"DataModelSchema": "{not json"})
    with pytest.raises(SchemaParseError):
        parse_datamodel_schema(str(p))


def test_parse_datamodel_schema_missing_model_key(tmp_path):
    p = tmp_path / "nomodel.pbit"
    _make_pbit(p, {"DataModelSchema": json.dumps({"foo": "bar"})})
    with pytest.raises(SchemaParseError, match="'model' key"):
        parse_datamodel_schema(str(p))


def test_parse_datamodel_schema_falls_back_to_next_candidate(tmp_path):
    """If the first matching file fails to parse, the loop must try the next
    candidate (extractor.py:172-189) rather than giving up immediately."""
    p = tmp_path / "fallback.pbit"
    _make_pbit(p, {
        "DataModel": "{not json",
        "DataModelSchema": json.dumps(VALID_SCHEMA),
    })
    schema = parse_datamodel_schema(str(p))
    assert schema == VALID_SCHEMA
