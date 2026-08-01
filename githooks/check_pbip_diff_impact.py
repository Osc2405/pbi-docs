#!/usr/bin/env python3
"""
Pre-commit guard for repos that version Power BI models (.pbip/.pbit):
blocks a commit that removes or modifies a measure or column other measures
still depend on (a broken DAX reference), using pbi-docs's own
`--diff --diff-impact --transitive`.

Reference implementation — see docs/pre_commit_hook.md for how to adopt this
in a repo that actually has .pbip/.pbit models. This repo (pbi-docs itself)
does not wire this hook up on itself: it only has static test fixtures, not
actively-edited models.

Compares STAGED content (the git index — respects a partial `git add`, not
just the working tree) against HEAD, for every distinct .pbip/.pbit/
.SemanticModel unit touched by the commit. `--diff` takes real filesystem
paths, not git refs, so both versions are materialized into temp directories
via `git archive` (HEAD) / `git write-tree` + `git archive` (staged).

Fail-open if pbi-docs isn't installed or crashes unexpectedly (see
docs/pre_commit_hook.md) so a broken local environment doesn't block
everyone's commits. Fail-closed only on an actual detected breaking impact.
Skip this check entirely with `git commit --no-verify`.
"""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional, Set

INSTALL_HINT = (
    "pbi-docs is not runnable - install it with `pip install pbi-docs` "
    "or `pip install -e .` (local dev). See docs/pre_commit_hook.md. "
    "Skipping this check for now (fail-open)."
)


# ---------------------------------------------------------------------------
# Pure logic (unit-testable without a real git repo)
# ---------------------------------------------------------------------------

def _detect_project_roots(staged_paths: List[str]) -> Set[str]:
    """Map staged file paths to the .pbip/.pbit/.SemanticModel unit that owns
    them, deduplicated. Anything under a .Report/ folder (PBIR — the visual
    report, not the data model) is ignored, matching this project's existing
    scope (CLAUDE.md section 1: PBIR parsing is explicitly out of scope)."""
    roots: Set[str] = set()
    for path in staged_paths:
        posix_path = path.replace("\\", "/")
        if posix_path.endswith(".pbit") or posix_path.endswith(".pbip"):
            roots.add(posix_path)
            continue
        parts = posix_path.split("/")
        sm_index = next((i for i, p in enumerate(parts) if p.endswith(".SemanticModel")), None)
        if sm_index is not None:
            roots.add("/".join(parts[: sm_index + 1]))
        # anything else (including *.Report/...) is ignored
    return roots


def _has_breaking_impact(diff: dict) -> bool:
    """`measures_removed_impact`/`measures_modified_impact` (and their column
    counterparts `columns_removed_impact`/`columns_modified_impact`) carry one
    entry per removed/modified measure or column regardless of whether
    anything still references it — `used_by` is what tells you the
    removal/change actually breaks something (diff.py). A non-empty list
    alone is not sufficient; an entry with an empty `used_by` is a safe
    removal."""
    for key in ("measures_removed_impact", "measures_modified_impact",
                "columns_removed_impact", "columns_modified_impact"):
        for entry in diff.get(key, []):
            if entry.get("used_by"):
                return True
    return False


def _format_impact_report(unit: str, diff: dict) -> str:
    lines = [f"  {unit}:"]
    for entry in diff.get("measures_removed_impact", []):
        used_by = entry.get("used_by") or []
        if not used_by:
            continue
        callers = ", ".join(f"{u['table']}[{u['name']}]" for u in used_by)
        lines.append(f"    REMOVED {entry['table']}[{entry['name']}] - still used by: {callers}")
    for entry in diff.get("measures_modified_impact", []):
        used_by = entry.get("used_by") or []
        if not used_by:
            continue
        callers = ", ".join(f"{u['table']}[{u['name']}]" for u in used_by)
        lines.append(f"    MODIFIED {entry['table']}[{entry['name']}] - used by: {callers}")
    for entry in diff.get("columns_removed_impact", []):
        used_by = entry.get("used_by") or []
        if not used_by:
            continue
        callers = ", ".join(f"{u['table']}[{u['name']}]" for u in used_by)
        lines.append(f"    REMOVED COLUMN {entry['table']}[{entry['name']}] - still used by: {callers}")
    for entry in diff.get("columns_modified_impact", []):
        used_by = entry.get("used_by") or []
        if not used_by:
            continue
        callers = ", ".join(f"{u['table']}[{u['name']}]" for u in used_by)
        lines.append(f"    MODIFIED COLUMN {entry['table']}[{entry['name']}] - used by: {callers}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Git plumbing (requires a real repo)
# ---------------------------------------------------------------------------

def _run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _staged_paths(repo_root: Path) -> List[str]:
    out = _run_git(repo_root, "diff", "--cached", "--name-only", "--diff-filter=ACMR")
    return [line for line in out.splitlines() if line]


def _extract_archive(repo_root: Path, ref: str, path: str, dest: Path) -> bool:
    """Extract `path` as of `ref` (commit-ish or tree-ish) into `dest`.
    Returns False if `path` doesn't exist at `ref` (e.g. brand-new project,
    nothing to compare against — git archive exits non-zero with an empty
    pathspec match)."""
    result = subprocess.run(
        ["git", "archive", "--format=zip", ref, "--", path],
        cwd=repo_root, capture_output=True,
    )
    if result.returncode != 0 or not result.stdout:
        return False
    zip_path = dest / "_archive.zip"
    zip_path.write_bytes(result.stdout)
    with zipfile.ZipFile(zip_path) as zf:
        if not zf.namelist():
            return False
        zf.extractall(dest)
    zip_path.unlink()
    return True


def _find_pbi_docs_cmd() -> Optional[List[str]]:
    """Prefer the `pbi-docs` console script; fall back to `python -m
    pbi_extractor.cli` if the package is importable but pip's Scripts/bin
    directory isn't on PATH (a common Windows gotcha) — same interpreter
    that's running this hook, so it's a meaningful fallback rather than a
    guess."""
    exe = shutil.which("pbi-docs")
    if exe is not None:
        return [exe]
    if importlib.util.find_spec("pbi_extractor") is not None:
        return [sys.executable, "-m", "pbi_extractor.cli"]
    return None


def _check_one_unit(repo_root: Path, unit: str, pbi_docs_cmd: List[str]) -> Optional[dict]:
    """Returns the diff dict if the unit existed in HEAD and pbi-docs ran
    successfully, else None (new project, or pbi-docs failed on this unit —
    caller decides how to treat that)."""
    with tempfile.TemporaryDirectory(prefix="pbip-hook-base-") as base_dir, \
         tempfile.TemporaryDirectory(prefix="pbip-hook-staged-") as staged_dir, \
         tempfile.TemporaryDirectory(prefix="pbip-hook-out-") as out_dir:
        base_dir, staged_dir, out_dir = Path(base_dir), Path(staged_dir), Path(out_dir)

        if not _extract_archive(repo_root, "HEAD", unit, base_dir):
            return None  # new project, nothing in HEAD to break

        tree_sha = _run_git(repo_root, "write-tree").strip()
        if not _extract_archive(repo_root, tree_sha, unit, staged_dir):
            return None  # staged version has nothing at this path (e.g. fully deleted)

        base_path = base_dir / unit
        staged_path = staged_dir / unit

        result = subprocess.run(
            [*pbi_docs_cmd, "--diff", str(base_path), str(staged_path),
             "--diff-impact", "--transitive", "-o", str(out_dir)],
            capture_output=True, text=True,
        )
        diff_path = out_dir / f"diff_{base_path.stem}_vs_{staged_path.stem}.json"
        if result.returncode != 0 or not diff_path.exists():
            print(f"Warning: pbi-docs failed comparing '{unit}': {result.stderr.strip()}", file=sys.stderr)
            return None
        return json.loads(diff_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        top_level = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("Warning: not inside a git repository (or git not found) - skipping pbip diff-impact check.")
        return 0
    repo_root = Path(top_level)

    staged = _staged_paths(repo_root)
    units = _detect_project_roots(staged)
    if not units:
        return 0  # nothing Power BI-shaped staged, don't even look for pbi-docs

    pbi_docs_cmd = _find_pbi_docs_cmd()
    if pbi_docs_cmd is None:
        print(f"Warning: {INSTALL_HINT}")
        return 0

    reports = []
    for unit in sorted(units):
        diff = _check_one_unit(repo_root, unit, pbi_docs_cmd)
        if diff is not None and _has_breaking_impact(diff):
            reports.append(_format_impact_report(unit, diff))

    if not reports:
        return 0

    print("pbip diff-impact check: this commit breaks measures/columns other measures depend on.\n")
    print("\n\n".join(reports))
    print(
        "\nFix the broken references, or update the dependents, before committing. "
        "To commit anyway: git commit --no-verify"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
