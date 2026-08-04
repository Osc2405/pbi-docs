# Git pre-commit hook: block commits that break measure/column dependencies

Reference implementation under [`githooks/`](../githooks/) for repos that version Power BI
models (`.pbip`/`.pbit`) and want a local, pre-commit gate on top of `pbi-context --diff
--diff-impact --transitive` — catching a removed or modified measure or column that other
measures still depend on, before it's committed.

This is a template to copy into **that** repo, not a hook this repo (`pbi-context`) runs on itself
— `pbi-context`'s own repository only has static test fixtures, not actively-edited Power BI models.

## What it does

1. Looks at what's **staged** for commit (`git diff --cached`, not the working tree — a partial
   `git add` is respected).
2. For every distinct `.pbip`/`.pbit`/`.SemanticModel` project touched, compares the staged
   version against `HEAD` using `pbi-context --diff --diff-impact --transitive`.
3. If a removed or modified measure or column is still referenced by another measure (`used_by`
   non-empty in the diff's `measures_removed_impact`/`measures_modified_impact`/
   `columns_removed_impact`/`columns_modified_impact`), it prints the detail and **blocks the
   commit** (exit 1).
4. If nothing Power BI-shaped is staged, or nothing broke, the commit proceeds normally.

`.Report/` (PBIR — the visual report definition) is ignored; only the semantic model is checked,
consistent with the rest of `pbi-context`'s scope.

## Install

One command per clone — `core.hooksPath` is a real git config option (git ≥ 2.9), no framework
needed:

```bash
git config core.hooksPath githooks
```

To remove it later: `git config --unset core.hooksPath`.

### Prerequisite: `pbi-context` itself

The hook shells out to the `pbi-context` command.

```bash
pip install pbi-context

# Or, from a local checkout of this repo (editable/dev install)
pip install -e .
```

If `pbi-context` isn't found on `PATH`, the hook falls back to `python -m pbi_extractor.cli` using
the same Python interpreter that's running the hook (handles the common case where pip's
`Scripts`/`bin` directory isn't on `PATH` but the package is still importable).

**If neither works, the hook fails open**: it prints a warning and lets the commit through rather
than blocking every contributor who hasn't installed `pbi-context` yet. It only blocks on an
*actual detected breaking impact*, never on its own missing prerequisites.

## Skip it for one commit

Git's native escape hatch already covers this — no custom flag needed:

```bash
git commit --no-verify -m "..."
```

## Why staged vs HEAD, not working tree vs HEAD

`pbi-context --diff` takes two filesystem paths, not git refs, so both versions have to be
materialized as real directories. The hook does this with `git archive` (for `HEAD`) and
`git write-tree` + `git archive` (for the index) into temp directories, rather than just pointing
at the working copy on disk — so a partial `git add` (staging only some of your changes) is
checked as what will *actually* be committed, not what happens to be sitting in your working
directory.

## Files

- `githooks/pre-commit` — the hook git actually executes. A thin POSIX `sh` shim (works under Git
  Bash on Windows) that just calls the Python script below.
- `githooks/check_pbip_diff_impact.py` — all the logic: detecting which projects changed,
  materializing base/staged versions, calling `pbi-context`, deciding pass/fail.

See `tests/test_githooks_pbip_diff.py` in the `pbi-context` repo for the test suite this was built
against, including real end-to-end cases (a temp git repo, a measure or column removed that
another measure references, asserting the commit is blocked).
