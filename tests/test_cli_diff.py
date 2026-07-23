"""CLI wiring tests for --diff / --diff-impact. The actual diff/impact
content is covered at the unit level in test_diff.py — these only confirm
the CLI plumbs args.diff_impact/args.transitive through to diff_impact()
and writes the result to disk."""

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.pbip"


def _run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "pbi_extractor.cli", *args],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )


def test_diff_without_impact_has_no_impact_keys(tmp_path):
    result = _run_cli("--diff", str(FIXTURE), str(FIXTURE), "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    diff_path = tmp_path / f"diff_{FIXTURE.stem}_vs_{FIXTURE.stem}.json"
    with open(diff_path, encoding="utf-8") as f:
        diff = json.load(f)
    assert "measures_removed_impact" not in diff
    assert "measures_modified_impact" not in diff


def test_diff_impact_flag_adds_impact_keys(tmp_path):
    result = _run_cli("--diff", str(FIXTURE), str(FIXTURE), "--diff-impact", "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
    diff_path = tmp_path / f"diff_{FIXTURE.stem}_vs_{FIXTURE.stem}.json"
    with open(diff_path, encoding="utf-8") as f:
        diff = json.load(f)
    # Same model compared against itself: no changes, so both impact lists are empty,
    # but the keys must be present — that's the wiring being tested here.
    assert diff["measures_removed_impact"] == []
    assert diff["measures_modified_impact"] == []


def test_diff_impact_combines_with_transitive(tmp_path):
    result = _run_cli("--diff", str(FIXTURE), str(FIXTURE), "--diff-impact",
                       "--transitive", "-o", str(tmp_path))
    assert result.returncode == 0, result.stderr
