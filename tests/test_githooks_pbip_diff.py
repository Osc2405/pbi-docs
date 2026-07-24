"""Tests for githooks/check_pbip_diff_impact.py — the reference pre-commit
hook that blocks a commit removing/modifying a measure other measures still
depend on (docs/pre_commit_hook.md).

Not part of the installable pbi_extractor package (githooks/ is a shippable
template for repos that version .pbip/.pbit models, imported here the same
way tests/test_resolver.py imports the dev-only scripts/generate_synthetic_pbip.py)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "githooks"))
import check_pbip_diff_impact as hook  # noqa: E402

FIXTURE_SM = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.SemanticModel"
FIXTURE_PBIP = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.pbip"
HOOK_SCRIPT = Path(__file__).parent.parent / "githooks" / "check_pbip_diff_impact.py"


# ---------------------------------------------------------------------------
# _detect_project_roots (pure, no git needed)
# ---------------------------------------------------------------------------

def test_detect_roots_pbit_file():
    roots = hook._detect_project_roots(["models/MyModel.pbit"])
    assert roots == {"models/MyModel.pbit"}


def test_detect_roots_pbip_file():
    roots = hook._detect_project_roots(["MyModel.pbip"])
    assert roots == {"MyModel.pbip"}


def test_detect_roots_semantic_model_subpath():
    roots = hook._detect_project_roots(
        ["MyModel.SemanticModel/definition/tables/Sales.tmdl"]
    )
    assert roots == {"MyModel.SemanticModel"}


def test_detect_roots_dedupes_multiple_files_same_project():
    roots = hook._detect_project_roots([
        "MyModel.SemanticModel/definition/tables/Sales.tmdl",
        "MyModel.SemanticModel/definition/tables/Date.tmdl",
        "MyModel.SemanticModel/definition/model.tmdl",
    ])
    assert roots == {"MyModel.SemanticModel"}


def test_detect_roots_ignores_report_files():
    roots = hook._detect_project_roots([
        "MyModel.Report/definition/pages/page1.json",
        "README.md",
    ])
    assert roots == set()


def test_detect_roots_multiple_distinct_projects():
    roots = hook._detect_project_roots([
        "ProjectA.SemanticModel/definition/tables/X.tmdl",
        "ProjectB.pbit",
    ])
    assert roots == {"ProjectA.SemanticModel", "ProjectB.pbit"}


def test_detect_roots_handles_windows_backslashes():
    roots = hook._detect_project_roots(
        ["MyModel.SemanticModel\\definition\\tables\\Sales.tmdl"]
    )
    assert roots == {"MyModel.SemanticModel"}


# ---------------------------------------------------------------------------
# _has_breaking_impact (pure, no git needed)
# ---------------------------------------------------------------------------

def test_has_breaking_impact_false_when_empty_lists():
    assert hook._has_breaking_impact(
        {"measures_removed_impact": [], "measures_modified_impact": []}
    ) is False


def test_has_breaking_impact_false_when_used_by_empty():
    """A non-empty measures_removed_impact list does NOT by itself mean
    something broke — each entry carries its own `used_by`, which can be
    empty (nobody referenced the removed/modified measure). This is the bug
    class this hook exists to get right (see CHANGELOG: cli.py's --diff
    used to silently corrupt this exact field when a_path/b_path shared a
    basename, always producing empty used_by)."""
    diff = {
        "measures_removed_impact": [{"table": "Sales", "name": "Unused", "used_by": []}],
        "measures_modified_impact": [],
    }
    assert hook._has_breaking_impact(diff) is False


def test_has_breaking_impact_true_for_removed():
    diff = {
        "measures_removed_impact": [
            {"table": "Sales", "name": "Total Sales",
             "used_by": [{"table": "Sales", "name": "YTD Sales"}]}
        ],
        "measures_modified_impact": [],
    }
    assert hook._has_breaking_impact(diff) is True


def test_has_breaking_impact_true_for_modified():
    diff = {
        "measures_removed_impact": [],
        "measures_modified_impact": [
            {"table": "Sales", "name": "Margin",
             "used_by": [{"table": "Sales", "name": "Margin %"}]}
        ],
    }
    assert hook._has_breaking_impact(diff) is True


# ---------------------------------------------------------------------------
# main() short-circuit behavior (in-process, monkeypatched — no real repo)
# ---------------------------------------------------------------------------

def test_main_skips_pbi_docs_lookup_when_nothing_staged(monkeypatch, tmp_path):
    monkeypatch.setattr(subprocess, "run",
                         lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=str(tmp_path), stderr=""))
    monkeypatch.setattr(hook, "_staged_paths", lambda repo_root: ["README.md"])

    called = {"n": 0}
    def _spy():
        called["n"] += 1
        return None
    monkeypatch.setattr(hook, "_find_pbi_docs_cmd", _spy)

    assert hook.main() == 0
    assert called["n"] == 0, "pbi-docs lookup must not happen when nothing pbip/pbit-shaped is staged"


def test_main_fails_open_when_pbi_docs_not_found(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(subprocess, "run",
                         lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=str(tmp_path), stderr=""))
    monkeypatch.setattr(hook, "_staged_paths", lambda repo_root: ["MyModel.pbit"])
    monkeypatch.setattr(hook, "_find_pbi_docs_cmd", lambda: None)

    assert hook.main() == 0
    assert "not runnable" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# End-to-end: real temp git repo, real pbi-docs subprocess call
# ---------------------------------------------------------------------------

def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    return repo


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        cwd=repo, capture_output=True, text=True,
    )


def _copy_fixture(repo: Path) -> Path:
    import shutil
    dest_sm = repo / "my-model.SemanticModel"
    shutil.copytree(FIXTURE_SM, dest_sm)
    shutil.copy(FIXTURE_PBIP, repo / "my-model.pbip")
    return dest_sm


@pytest.fixture
def committed_repo(tmp_path):
    repo = _init_repo(tmp_path)
    sm_dir = _copy_fixture(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)
    return repo, sm_dir


def test_hook_blocks_commit_that_breaks_a_dependent_measure(committed_repo):
    repo, sm_dir = committed_repo
    sales_tmdl = sm_dir / "definition" / "tables" / "Sales.tmdl"
    text = sales_tmdl.read_text(encoding="utf-8")
    # Total Sales is referenced by YTD Sales's DAX ([Total Sales]) in this fixture.
    assert "measure 'Total Sales' = SUM(Sales[SalesAmount])" in text
    text = text.replace(
        "\tmeasure 'Total Sales' = SUM(Sales[SalesAmount])\n\t\tformatString: $#,0\n\n",
        "",
    )
    sales_tmdl.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = _run_hook(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert "Total Sales" in result.stdout
    assert "YTD Sales" in result.stdout


def test_hook_allows_non_breaking_change(committed_repo):
    repo, sm_dir = committed_repo
    sales_tmdl = sm_dir / "definition" / "tables" / "Sales.tmdl"
    text = sales_tmdl.read_text(encoding="utf-8")
    text = text.replace(
        "\tmeasure 'Total Sales' = SUM(Sales[SalesAmount])\n\t\tformatString: $#,0\n",
        "\tmeasure 'Total Sales' = SUM(Sales[SalesAmount])\n\t\tformatString: $#,0\n\n"
        "\tmeasure 'Row Count' = COUNTROWS(Sales)\n\t\tformatString: 0\n",
    )
    sales_tmdl.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = _run_hook(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_hook_allows_brand_new_project(tmp_path):
    """A project with no prior version in HEAD has nothing to break."""
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("hello\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=repo, check=True)

    _copy_fixture(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = _run_hook(repo)

    assert result.returncode == 0, result.stdout + result.stderr


def test_hook_noop_when_nothing_pbip_staged(committed_repo):
    repo, _ = committed_repo
    (repo / "README.md").write_text("unrelated change\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    result = _run_hook(repo)

    assert result.returncode == 0, result.stdout + result.stderr
