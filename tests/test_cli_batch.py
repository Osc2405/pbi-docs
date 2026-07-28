"""Tests for `--batch` (cli.py). No test previously exercised this flag at all
(see Pruebas/auditoria_general_2026-07-24.md, P0 #2)."""

import json
import zipfile

from pbi_extractor.cli import main

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


def _make_pbit(path, schema=VALID_SCHEMA) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("DataModelSchema", json.dumps(schema))


def test_batch_no_matches_returns_error(tmp_path, capsys):
    out_dir = tmp_path / "out"
    rc = main(["--batch", str(tmp_path / "nothing" / "*.pbit"), "-o", str(out_dir)])
    assert rc == 1


def test_batch_processes_all_matches(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _make_pbit(data_dir / "a.pbit")
    _make_pbit(data_dir / "b.pbit")
    out_dir = tmp_path / "out"

    rc = main(["--batch", str(data_dir / "*.pbit"), "-o", str(out_dir)])

    assert rc == 0
    assert (out_dir / "a.pbit" / "metadata.json").exists()
    assert (out_dir / "b.pbit" / "metadata.json").exists()

    with open(out_dir / "a.pbit" / "metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)
    assert metadata["summary"]["total_tables"] == 1


def test_batch_partial_failure_still_processes_valid_files(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    _make_pbit(data_dir / "good.pbit")
    (data_dir / "bad.pbit").write_bytes(b"not a zip file")
    out_dir = tmp_path / "out"

    rc = main(["--batch", str(data_dir / "*.pbit"), "-o", str(out_dir)])

    assert rc == 1  # not all items succeeded
    assert (out_dir / "good.pbit" / "metadata.json").exists()
    # output_dir is created before extraction is attempted, so the folder may
    # exist, but it must never contain a metadata.json for a failed extraction.
    assert not (out_dir / "bad.pbit" / "metadata.json").exists()
