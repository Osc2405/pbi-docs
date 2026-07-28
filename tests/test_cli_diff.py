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


def test_diff_impact_finds_real_usages_when_models_share_a_basename(tmp_path):
    """Regression test: a_path/b_path sharing a basename (e.g. two checkouts of
    the same project — the single most common real-world diff scenario) used
    to make process_file() silently overwrite a's output with b's before
    diff_impact() read it back, so every `used_by` came back empty regardless
    of real dependencies (see CHANGELOG). test_diff_impact_flag_adds_impact_keys
    above only diffs FIXTURE against itself, which can't distinguish the bug
    from the correct answer (both give empty impact) — this test uses two
    *different* copies with a genuine broken dependency (Total Sales removed,
    still referenced by YTD Sales's DAX) to catch it for real."""
    import shutil

    a_dir = tmp_path / "checkout_a"
    b_dir = tmp_path / "checkout_b"
    shutil.copytree(FIXTURE.parent, a_dir)
    shutil.copytree(FIXTURE.parent, b_dir)

    sales_tmdl = b_dir / "my-model.SemanticModel" / "definition" / "tables" / "Sales.tmdl"
    text = sales_tmdl.read_text(encoding="utf-8")
    assert "measure 'Total Sales' = SUM(Sales[SalesAmount])" in text
    text = text.replace(
        "\tmeasure 'Total Sales' = SUM(Sales[SalesAmount])\n\t\tformatString: $#,0\n\n", "")
    sales_tmdl.write_text(text, encoding="utf-8")

    out_dir = tmp_path / "out"
    result = _run_cli("--diff", str(a_dir / "my-model.pbip"), str(b_dir / "my-model.pbip"),
                       "--diff-impact", "--transitive", "-o", str(out_dir))
    assert result.returncode == 0, result.stderr

    diff_path = out_dir / "diff_my-model_vs_my-model.json"
    with open(diff_path, encoding="utf-8") as f:
        diff = json.load(f)

    removed_impact = {(e["table"], e["name"]): e["used_by"] for e in diff["measures_removed_impact"]}
    assert ("Sales", "Total Sales") in removed_impact
    used_by_names = {(u["table"], u["name"]) for u in removed_impact[("Sales", "Total Sales")]}
    assert ("Sales", "YTD Sales") in used_by_names
