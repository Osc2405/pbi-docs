# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`--diff-impact` extended to columns**: `resolver.find_column_usages(model_dir, table_name, column_name, *, transitive=False)` — impact analysis for a column (which measures reference it in their DAX, directly or transitively), mirroring `find_measure_usages()`. No `find_column_dependencies()` counterpart: a column has no DAX expression of its own in this model, so "what does a column depend on" doesn't apply.
- `diff.diff_impact()` now also returns `columns_removed_impact`/`columns_modified_impact` alongside the existing `measures_removed_impact`/`measures_modified_impact` — same old-model/new-model lookup rule (removed → old model, modified → new model). `cli.py`'s `--diff --diff-impact` and `diff.diff_with_impact()` needed no changes, both already generic over whatever keys `diff_impact()` returns.
- New MCP tool `find_column_usages` (thin wrapper over the resolver function, same shape as `find_measure_usages`); `diff_impact` tool description updated to mention column impact.
- `githooks/check_pbip_diff_impact.py`: `_has_breaking_impact()`/`_format_impact_report()` now also check `columns_removed_impact`/`columns_modified_impact` — the hook previously only blocked measure-breaking commits, letting a removed/modified column that a measure's DAX still references through silently.
- **Mermaid ER diagram embedded in `model_documentation.md`**: `documentation.generate_mermaid_er(cleaned_metadata)` renders a simplified entity-relationship diagram (crow's-foot cardinality, solid/dotted line for active/inactive) directly from the relationships already in `cleaned_metadata` — no new extraction. Isolated tables (no relationships) are omitted. New i18n key `diagram_isolated_note` (en/es).

### Documentation

- `docs/fabric_compatibility.md`: documents *expected* TMDL compatibility with Microsoft Fabric semantic models, based on the shared public TMDL spec — explicitly marked as not empirically validated (no real Fabric export available in this environment), same treatment as other external blockers (`docs/human_validation_protocol.md`, Anthropic token counting).
- `.mcp.json` now points at `output/Sales Sample` instead of `output/Supply Chain Sample` (decided in an earlier session, executed now); `docs/use-cases.md` MCP server section updated to match (also fixed a stale "9 tools" count left over from the `find_column_usages` addition — should have been 10).
- **`--export-graph` CLI flag**: new `pbi_extractor/graph_export.py` (`build_graph()`, `to_graphml()`) projects an already-processed model's tables/relationships to a generic `{nodes, edges}` graph, as `--query` mode JSON (default) or GraphML XML (`--export-graph graphml`) for external tools (Gephi, yEd). Not exposed as an MCP tool — deliberate scope decision, see `CLAUDE.md`.
- **`docs/index.schema.json`**: formal JSON Schema (draft 2020-12) for `index.json`, formalizing the shape already documented in prose in `docs/index-json-spec.md`. Validated in `tests/test_indexed_output.py` against real `build_index()` output (json/toon/auto) using the `jsonschema` library, now a dev-only test dependency (`pyproject.toml` `dev` extras) — the published package remains zero-dependency.

## [1.0.1] - 2026-08-03

### Changed

- **Renamed to `pbi-context`.** This is the final release published under the `pbi-docs` name on
  PyPI — no functional changes from `1.0.0`. Reason: `pbi-docs` collided with an unrelated,
  pre-existing GitHub project of the same name (`alisonpezzott/pbi-docs`, a Power BI tenant-wide
  REST API/DAX Studio documentation scraper with real audience reach), creating a real SEO/
  discoverability ambiguity even though the two tools share no architecture or feature overlap.
  Continued development, the actual `1.1.0` feature release (columns diff-impact, Mermaid ER
  diagram, `--export-graph`, real-tokenizer validation, pre-commit hook), and all future releases
  live at [`pbi-context`](https://github.com/Osc2405/pbi-context) /
  `pip install pbi-context`. See `PYPI_RENAMED_NOTICE.md`.

## [1.0.0] - 2026-07-28

### Added

- **PBIP / TMDL format support** (`pbi_extractor/pbip_extractor.py`)
  - New `parse_pbip_model(input_path)` function returns the same `raw_schema` dict structure as the existing `.pbit` extractor, so all downstream modules (`processor.py`, `formatters.py`, `categorizer.py`, etc.) work without changes.
  - TMDL parser: line-by-line, tab-aware, zero external dependencies.
  - Supports: table declarations, column properties (`dataType`, `formatString`, `sourceColumn`, `isHidden`), single-line and multi-line measure DAX, relationship blocks in `model.tmdl`, `compatibilityLevel` from `database.tmdl`.
  - Three entry points accepted: `.pbip` marker file, `.SemanticModel/` folder directly, or project root folder containing a `.SemanticModel/` subfolder.
  - Graceful degradation for unsupported constructs (annotations, hierarchies, report pages) — they are silently skipped.
  - Custom exception hierarchy: `PBIPExtractionError`, `SemanticModelNotFoundError`, `TmdlParseError`.

- **Auto-detection of input format** (`cli.py :: detect_input_format`)
  - Automatically detects `.pbit` vs `.pbip` from file extension or folder structure.
  - `--input` now accepts files and folders (not just `.pbit` files).
  - `--diff` and `--batch` support mixed formats in the same invocation.

- **Multi-file indexed output** (`pbi_extractor/indexed_output.py`)
  - New `write_indexed_output()` writes three additional files per model run (additive, does not break existing consumers of `metadata.json`, `agent_context.json`, `model_context.jsonl`):
    - `index.json` — lightweight model summary with per-table metadata (column/measure counts, category list, relative path to detail file) and a `files` section pointing to all other artifacts.
    - `tables/<TableName>.json` — full table detail: all columns + all measures including formatted DAX.
    - `relationships.json` — all relationships in a focused single file.
  - Table filenames are sanitized to be filesystem-safe.
  - `index.json` includes a `source_format` field (`"pbit"` or `"pbip"`).

- **`--index-format` CLI flag**
  - Accepts `json` (default) or `toon`.
  - Wired through `process_file()` to `write_indexed_output()`.

- **TOON serialization** (`pbi_extractor/toon_encoder.py`)
  - New `encode_toon(records, fields) -> dict` and `decode_toon(toon_block) -> list[dict]`.
  - Format: `{"__toon": true, "__fields": [...], "__rows": [[...], ...]}` — field names declared once, data as rows.
  - Applied via `--index-format toon` to:
    - `columns` in `tables/<Name>.json` (fields: name, data_type, category, is_hidden, source_column, format_string)
    - `measures_flat` in `tables/<Name>.json` (fields: name, category, complexity, is_hidden, format_string, display_folder)
    - `relationships.json` (fields: from_table, from_column, to_table, to_column, cardinality, cross_filtering, is_active)
  - DAX body (`measures_dax`) remains plain JSON in all modes — never TOON.
  - `agent_context.json`, `metadata.json`, `model_context.jsonl` never affected.
  - When TOON active, `tables/<Name>.json` uses `measures_flat` + `measures_dax` instead of a single `measures` array.
  - `index.json` gains a top-level `"index_format"` field (`"json"` or `"toon"`) so consumers can detect format without inspecting the data files.

- **Test coverage for PBIP/TOON** (93 tests total, up from 22)
  - `tests/test_pbip_extractor.py` — 33 tests covering TMDL parsing, entry points, processor compatibility, parity, and error handling.
  - `tests/test_cli_detection.py` — 11 tests for format auto-detection and model name extraction.
  - `tests/test_indexed_output.py` — 16 tests for `build_index`, `write_indexed_output`, file existence, content, and non-regression checks.
  - `tests/fixtures/minimal_pbip/` — minimal TMDL fixture model (3 tables, 3 measures, 2 relationships) used across all new tests.

- **`--index-format auto`** (`pbi_extractor/indexed_output.py`) — per-table TOON/JSON selection instead of one global format for the whole model. `_should_use_toon(table)` decides per table on `len(columns) + len(measures)` against an empirically-measured threshold (5 rows still loses to JSON, 7 already wins — see `docs/token_optimization_report.md` section 4; the roadmap doc's earlier "~10 rows" guess was replaced with the real number). Each `index.json` table entry now carries its own `"format": "json"|"toon"` field — the top-level `index_format` becomes `"auto"` as a signal to check per-table. `resolver.py :: get_table()` needed no changes: it already detects format per file by shape (`measures_flat` presence), not by a declared field.

- **`index.json` documented as an open format spec** (`README.md`) — full schema for the top-level file and both `tables/<Name>.json` shapes (plain JSON and TOON), so other tools can be built against it without reading `pbi_extractor` source. Includes a versioning rule (`version: "1"`, bump on incompatible shape changes).

- **Resolver dependency / impact-analysis queries** (`pbi_extractor/resolver.py`) — Horizonte 3's "compound questions" item. Regex-based (not a DAX parser) over `formatted_expression`, matching `'Table'[Column]`, `Table[Column]`, and standalone `[Measure]` references.
  - `get_measure_dependencies(model_dir, table, measure)` — what a measure references (other measures + columns).
  - `find_measure_usages(model_dir, table, measure)` — inverse: which measures reference this one (impact analysis).
  - Both accept `transitive=True` to follow the chain via cycle-safe BFS instead of stopping at one hop, returning the full closure of what's touched/affected directly or indirectly. `transitive=False` (default) is byte-for-byte unchanged from the one-hop behavior — verified with explicit non-regression tests.
  - Exposed as 2 new MCP tools (`get_measure_dependencies`, `find_measure_usages`, with an optional `transitive` boolean on both) and 3 new `--query` CLI flags: `--dependencies`, `--usages`, `--transitive`.
  - Found and fixed a real-world PBIP sample bug along the way (see Fixed, below) while building the fixtures used to validate this.

- **Real token-count script** (`scripts/count_tokens.py`) — standalone, not part of the `pbi_extractor` package or `pyproject.toml` (same treatment as Graphify, `CLAUDE.md` section 3): uses the Anthropic API's `count_tokens` endpoint to replace the bytes÷4 approximation in `docs/token_optimization_report.md`. Requires `pip install anthropic` + `ANTHROPIC_API_KEY` only if you choose to run it — not evaluated in this environment (no key available), documented as blocked rather than simulated.

- **`files_test/Sales Sample.pbip`** — official Microsoft PBIP sample (`microsoft/Analysis-Services`, MIT license), downloaded byte-exact. 11 tables, 29 measures, 5 relationships (incl. calculation-group-style tables, DAX variables, an inactive relationship) — used as the medium-size model for `docs/human_validation_protocol.md` and as the source of real 3+-level measure chains in the transitive-dependency tests above.

- **`docs/human_validation_protocol.md`** — executable protocol for the Horizonte 3 human validation experiment (`docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md` section 6's "próximo paso crítico"): 3 conditions (raw TMDL / pbi-docs JSON / MCP-Resolver), between-subjects design, data-collection template, grading rubric, and a 20-question set with reference answers computed from `Sales Sample`'s `metadata.json`.

- **Chat-invocable Skills for analyzing a model without leaving the IDE**
  - `.claude/skills/analyze-pbi-model/SKILL.md` — Claude Code project skill; runs the extractor and teaches progressive loading of the indexed output (`index.json` first, `--query` for anything scoped).
  - `.github/prompts/analyze-pbi-model.prompt.md` — equivalent GitHub Copilot (VS Code) prompt file, same strategy.

- **Query resolver + `--query` CLI mode** (`pbi_extractor/resolver.py`) — precursor to an MCP server: structured, on-demand access to an already-processed output directory, normalizing JSON vs TOON transparently so callers never see the `{__toon, __fields, __rows}` wrapper.
  - `list_tables()`, `get_table()`, `get_relationships()`, `search_measures()` — stdlib only, zero new dependencies.
  - `get_table()` merges `measures_flat` + `measures_dax` (or the plain-JSON measure list) into one canonical shape regardless of source `--index-format`.
  - `search_measures()` is a genuinely new capability — finding "which tables have a revenue measure" previously required opening every table file by hand.
  - CLI: `pbi-docs --query <output-dir> --list-tables|--table NAME [--measure NAME]|--search-measures QUERY|--search-columns QUERY|--relationships [--table NAME]`, printing JSON to stdout.
  - Both Skills above updated to call `--query` instead of reading `tables/*.json` directly.
  - `get_measure()` and `search_columns()` added, rounding out the tool surface: single-measure lookup and column search (mirrors `search_measures()`).

- **Automated precision validation** (`docs/precision_validation_report.md`) — a proxy for the analysis doc's Horizonte 3 human-tester experiment: 3 isolated agents answer the same 18 objectively-gradable questions using only raw TMDL, only pbi-docs JSON, or only `--query`, respectively. Result: JSON and `--query` both scored 18/18; raw TMDL scored 16/18, with both misses being honest `NOT_FOUND` on a field (measure category) that doesn't exist in TMDL at all — a structural limitation of the source format, not an agent error.

- **Read-only MCP server** (`pbi_extractor/mcp_server.py`) — hand-rolled against the stable spec (`2025-06-18`, newline-delimited JSON-RPC 2.0 over stdio), no `mcp` SDK dependency (that package pulls in pydantic/anyio/httpx/starlette/uvicorn, contradicting this project's zero-dependency stance).
  - One server instance bound to one already-processed model directory; 6 tools, thin wrappers around `resolver.py`: `list_tables`, `get_table`, `get_measure`, `search_measures`, `search_columns`, `get_relationships`.
  - CLI: `pbi-docs --mcp-serve <output-dir>`.
  - Deliberately read-only — no DAX execution, no model editing; complementary to Microsoft's Modeling MCP (writes) and Remote MCP (executes DAX), per `docs/Analisis_Posicionamiento_Comparativa_Plan_Futuro.md`'s positioning.
  - `.mcp.json` added at the project root — a dev/demo convenience for validating the server against a real MCP client (Claude Code), pointed at the `Supply Chain Sample` fixture. See README section 7 for manual verification steps. **Not yet confirmed against a live client** — all automated coverage (`tests/test_mcp_server.py`) exercises the protocol via a subprocess harness I wrote myself, not a real MCP client's discovery/call path. This is the one gap in the MCP feature that can't be closed by an automated test alone.

- **`scripts/generate_synthetic_pbip.py`** (dev-only, not packaged — same treatment as `scripts/count_tokens.py`) — generates a synthetic star-schema PBIP/TMDL project at a configurable scale (default 20 dimension + 40 fact tables) for scale-validation runs, used because no free/public PBIP project at enterprise scale could be found (checked 8 repos; all converge on the same ~10-table teaching model already in `files_test/`).
- **`docs/scale_validation_report.md`** — Fase 0 of the context/audit-layer roadmap: timing, `index.json` size, and TOON-threshold behavior measured against a 60-table/288-measure synthetic model. Key findings: `--index-format auto` converges to pure `toon` at this scale (every table exceeds the 7-row threshold); the "specific table" and "deep-dive" token-savings scenarios from `token_optimization_report.md` (validated on 7 tables) invert at 60 tables because `index.json`'s per-table fixed cost grows with table count; `resolver.get_measure_dependencies`/`find_measure_usages` with `transitive=True` re-reads every table from disk on each BFS hop (0.002s → 1.6s going from a single lookup to a transitive one on this model) — root-caused and partially fixed, see Fixed below.
- **Content-aware `--diff`** (Fase 1 of the context/audit-layer roadmap, `pbi_extractor/diff.py`) — `diff_models()` previously only diffed *existence* (measure/relationship added or removed by identity tuple), with zero column support and zero DAX/format comparison. Now adds `measures_modified`, `columns_added`/`removed`/`modified`, and `relationships_modified`, each entry carrying a `changes` dict of `{field: {old, new}}`. DAX changes on `formatted_expression` are additionally tagged `"semantic"` or `"cosmetic"` via a whitespace-insensitive comparison (`_normalize_dax`) — documented as a text heuristic, not a DAX parser. `tests/test_diff.py` (11 tests) is the correctness gate for this deterministic logic — no separate empirical "precision report" needed, unlike the LLM-facing validation reports, since there's no non-determinism to measure here. `cli.py`'s `--diff` now also logs an added/removed/modified summary line per category.

- **`--diff-impact`**: combine with `--diff` to report which measures reference each
  removed/modified measure (impact analysis), on top of the content-aware diff above.
  Combine with `--transitive` to follow the dependency chain beyond one level.
  - `diff.diff_impact(diff, model_dir_a, model_dir_b, *, transitive=False)` and
    `diff.diff_with_impact(model_dir_a, model_dir_b, *, transitive=False)` connect `diff.py`
    (previously independent of `resolver.py`) to `resolver.find_measure_usages()`.
  - `resolver.load_metadata(model_dir)`: reads `metadata.json` from an already-processed output
    directory — needed by the model_dir-based diff wrappers.
  - MCP server: new `diff_impact` tool (server now exposes 9 tools) — lets an AI agent ask "what
    changed between these two model versions, and what might break" without leaving the MCP
    session.

- **Gemini provider in `scripts/count_tokens.py`** (`--provider gemini`, dev-only script, not part of the package or `pyproject.toml` — same treatment as Graphify, `CLAUDE.md` section 3) — real token counts via the free-tier Gemini API (`google-genai` SDK), alongside the existing Anthropic provider. Used to replace the chars÷4 approximation in `docs/token_optimization_report.md` with real figures across all 3 scenarios on `Supply Chain Sample.pbip`: confirms the approximation's direction but underestimates pbi-docs's real savings by 5-27 points — most notably, TOON's aggregate advantage over JSON is real and substantial (-22.4%) where the approximation showed it as marginal (-3.4%).

- **Reference git pre-commit hook** (`githooks/`, not part of the installable package — a template for repos that version `.pbip`/`.pbit` models, see `docs/pre_commit_hook.md`) — blocks a commit that removes or modifies a measure another measure still depends on, using `pbi-docs --diff --diff-impact --transitive` under the hood. Compares *staged* content against `HEAD` (not the working tree — respects a partial `git add`) by materializing both versions via `git archive`/`git write-tree` into temp directories, since `--diff` takes filesystem paths, not git refs. Fails open (warns, lets the commit through) if `pbi-docs` isn't installed or crashes unexpectedly, and blocks (exit 1) only on an actual detected breaking impact. Skip per-commit with git's native `--no-verify`, no custom flag needed. Install with `git config core.hooksPath githooks`. 17 tests in `tests/test_githooks_pbip_diff.py`, including real end-to-end cases (temp git repo, real `pbi-docs` subprocess call).

- **Real answer-quality validation experiment** (`scripts/answer_quality_gemini.py`, dev-only, same treatment as above) — tests whether pbi-docs's compressed context preserves answer correctness, not just token savings, using real Gemini function calling (not Claude Code subagents) against 20 business questions on `Sales Sample.pbip` (11 tables/29 measures). Results: 70%/90%/95% accuracy for raw TMDL / pbi-docs JSON / function-calling conditions respectively — the function-calling condition wins on accuracy AND token cost simultaneously (89.9% token reduction vs. raw TMDL, no trade-off between cheap and correct). See `docs/answer_quality_gemini_report.md`. Question set reused from `docs/human_validation_protocol.md` section 5, with one reference answer corrected after the experiment found it incomplete.

### Changed

- **Indexed output (`index.json`, `tables/*.json`, `relationships.json`) is compact by default**,
  not indented. These files are meant for `resolver.py`/`mcp_server.py`/LLM consumption, not
  human reading — the human-readable artifact is `model_documentation.md`. Measured on a 60-table
  synthetic model: -44.3% on the "deep-dive" scenario (`docs/scale_validation_report.md` section
  5.2), confirming the projection already documented in section 5.1.
  - New `--pretty` CLI flag restores the previous `indent=2` behavior for human debugging.
  - `write_indexed_output()` and `process_file()` gain a `pretty: bool = False` parameter.
- `cli.py :: process_file()` now accepts an `index_format` parameter and calls `write_indexed_output()` after the existing pipeline steps.
- `cli.py :: main()` updated description from "`.pbit`" to "`.pbit` / `.pbip`"; removed the hardcoded `.pbit`-extension validation for `--input`.
- Output directory naming for PBIP: uses clean model name (e.g., `my-model/`) instead of `my-model.pbit/`. PBIT behavior is unchanged for backward compatibility.
- CLI help text and usage examples updated to include PBIP examples and `--index-format`.
- **Relationship diff identity** (`pbi_extractor/diff.py`) — a relationship's identity for diffing is now `(from_table, from_column, to_table, to_column)` instead of also including `cardinality`/`cross_filtering` in the identity tuple. Effect: a relationship that keeps the same connected columns but changes cardinality/cross-filtering/active flag now appears once in `relationships_modified` instead of once each in `relationships_added` and `relationships_removed`. No prior test coverage depended on the old behavior.

### Fixed

Bugs found and fixed while validating PBIP/TMDL support against a real (non-synthetic) `.pbip` export:

- `pbip_extractor.py`: TMDL files live under `<SemanticModel>/definition/`, not directly in `.SemanticModel/` — the extractor was silently finding 0 tables against real exports.
- `pbip_extractor.py`: `_parse_table_column_ref` didn't strip quotes from a column name when the table part was unquoted (e.g. `Explanations.'Product ID'`).
- `pbip_extractor.py`: single-line and multi-line calculated columns (`column 'Name' = <DAX>`) left the DAX expression glued onto the column name instead of splitting it off, mirroring the existing measure-parsing logic.
- `pbip_extractor.py`: relationship parsing generalized (`_parse_relationships_tmdl`) to support both layouts real exports use — relationships embedded in `model.tmdl` and the standalone `relationships.tmdl` file.
- `documentation.py`: `model_documentation.md` rendered an empty `### TableName` header (no columns, no measures) when a visible table had every column individually hidden — the table is now skipped entirely in that case.
- `tests/fixtures/minimal_pbip/` migrated to the `definition/` layout to reflect real PBIP structure; added regression tests for all of the above.
- `cli.py`: `resolver.get_measure()` and `resolver.search_columns()` existed (and were exposed as MCP tools) but were never wired into `--query`'s argparse/dispatch — found during the precision validation run above, when the MCP-condition agent hit an argparse error and had to work around it by loading whole tables instead. Added `--measure` and `--search-columns` flags; 2 new regression tests.
- `pbip_extractor.py`: measures using TMDL's backtick-fenced multi-line DAX form (`` measure X = ``` ``...`` ``` `` — used by Tabular Editor and various DAX formatters) were extracted as the literal `` ``` `` string instead of the real expression, because the parser's single-line-vs-multi-line branch only recognized the bare `measure X =` form, not `= \`\`\``. Found while downloading `files_test/Sales Sample.pbip` for the human validation experiment — 7 of its measures were affected. Fixed; regression test `test_parse_measure_backtick_fenced_dax`.
- `mcp_server.py` called `logging.basicConfig()` at module import time. Since `cli.py` does `from . import mcp_server` unconditionally, this silently hijacked the *entire* CLI's logging — not just `--mcp-serve` — because `logging.basicConfig()` is a no-op after the first call in a process. Effect: every log line was mislabeled `mcp_server` instead of `__main__`, and `--verbose` stopped showing DEBUG output CLI-wide. Moved the config into `run()`, gated so it only applies when nothing has configured logging yet (i.e. when running standalone via `python -m pbi_extractor.mcp_server`, not when dispatched through `cli.py`). Found while wiring up `.mcp.json` for real-client validation; regression test added (`test_importing_mcp_server_does_not_break_cli_logging`).
- **`resolver._extract_references` misclassified an unqualified `[Column]` DAX reference as a measure reference** (`pbi_extractor/resolver.py`) — found running `pbi-docs` against two real-world PBIP exports (`file_test_2/`, not part of the repo's test fixtures) as an ad hoc validation of the current state. Corporate Spend's `Fact[Amount] = TOTALYTD(SUM([Value]), 'Date'[Date])*.3` references `Fact[Value]`, a column on the same table — valid DAX, since a bare `[X]` inside an expression belonging to table T can mean either a measure named X or an unqualified reference to T's own column X. The regex had no way to tell them apart and always treated bare brackets as measures, so `get_measure_dependencies()`/`find_measure_usages()` reported `Value` under `references_measures` instead of `references_columns`. Neither of the repo's existing fixtures (`tests/fixtures/minimal_pbip/`, `files_test/Sales Sample.pbip`) happened to contain a measure that references a same-table column without the `Table[Column]` qualifier, so this never surfaced before. Fixed by threading each measure's owning table name and real column set through to `_extract_references()`; a bare `[X]` is now only classified as a measure if no column named X exists on the owning table. `tests/test_resolver.py` gains two direct unit tests against `_extract_references()` covering both branches rather than growing the shared `minimal_pbip` fixture, since that fixture is read by several other test files and a new measure there would have shifted unrelated counts (`test_indexed_output.py`, `test_pbip_extractor.py`, `test_toon_encoder.py`).
- **`resolver.get_table()` always loaded the full `index.json` before reading the requested table** (`pbi_extractor/resolver.py`) — the finding from `docs/scale_validation_report.md` section 4 ("tabla específica"/"deep-dive" scenarios inverting at 60-table scale because `index.json`'s per-table fixed cost outweighed the table being fetched), root-caused and partially fixed. The table's filename is fully determined by `_safe_filename(table_name)`, so a point lookup never needed the index at all — it only read it because the code was written to validate existence that way. Now `get_table()` reads `tables/<name>.json` directly first (with a name-match guard against `_safe_filename` collisions between differently-named tables); `index.json` is only loaded as a fallback to build the "Available tables" error list when the direct read misses. `get_measure()` and the non-transitive branch of `get_measure_dependencies()` delegate to `get_table()`, so they inherit the fix for free. Re-measured on the same 60-table synthetic model: "tabla específica" drops from 10.34x to 2.00x the size of raw TMDL — a large improvement, but not a net win on this particular synthetic model, whose generator produces clean TMDL with no `lineageTag`/`annotations` noise to strip (unlike the real `Supply Chain Sample.pbip` the original 91%/35.4% savings figures came from). "Deep-dive completo" is unaffected by design (`list_tables()` genuinely needs the full table listing, so it correctly still reads `index.json`) and remains inverted (2.48x); dropping `json.dump(..., indent=2)` was measured (not implemented) as a candidate fix — 44.3% size reduction, bringing the ratio to 1.38x, still not a full reversal — and left as an open, evidence-backed finding rather than an untested guess. `docs/scale_validation_report.md` section 5.1 has the full write-up and numbers. Two new regression tests in `tests/test_resolver.py` assert `load_index()` is not called on the `get_table()`/`get_measure()` happy path.
- **`resolver.find_measure_usages(transitive=True)` re-read the entire model from disk on every BFS hop** (`pbi_extractor/resolver.py`) — the finding from `docs/scale_validation_report.md` section 5. `_all_measures(model_dir)` is now fetched once per call and reused across all hops instead of being re-fetched inside the recursive single-hop helper. Verified deterministically (`tests/test_resolver.py::test_find_measure_usages_transitive_reads_model_once_not_per_hop`, asserts the call count is exactly 1 via monkeypatch) rather than by a wall-clock threshold, which was flaky across cold/warm filesystem cache.
- **`scripts/generate_synthetic_pbip.py` generated duplicate measure names across fact tables** (e.g. every `FactNN` table had its own `"Total Amount1"`) — found while trying to get a clean before/after timing number for the fix above. A real Tabular model never allows this (measure names are unique model-wide); the collision was silently inflating `find_measure_usages`'s BFS with false cross-table matches, which means the original 1.6s figure in `docs/scale_validation_report.md` mixed the real per-hop re-read cost with this generator artifact. Fixed by prefixing numeric column names with the table name (`Fact01Amount1` instead of `Amount1`) so derived measure names are naturally unique. See `docs/scale_validation_report.md` section 5 for the full correction — no clean re-measured wall-clock number is presented as a replacement, the call-count test is the validation instead.
- **`model_documentation.md` polished for human readability** (`pbi_extractor/documentation.py`): removed dead code (`category_icons`, built but never read), unified measure-category heading levels (`####` consistently, instead of jumping to `#####` inside a table but `####` in the closing summary), removed the per-measure `---` separator (was repeating once per measure, noisy in models with many measures per category — a single blank line already delimits them; `---` is now reserved for top-level section breaks only), and removed the "Key Measures Available" closing summary, which duplicated (with less detail, and only 7 of 10 categories) the same measures already listed with full DAX earlier in the same document.

- **`--diff --diff-impact` silently corrupted its own `used_by` field whenever `a_path` and `b_path` shared a basename** — found while building the pre-commit hook above, whose entire premise (staged vs HEAD of the *same* project) is exactly this case. `cli.py`'s `--diff` handling wrote both `process_file()` outputs to `output_base/<model_name>`, where `<model_name>` comes from `_get_model_name()`'s basename-only logic — so comparing two checkouts of the same project (the single most common real-world diff scenario) had the second `process_file()` call silently overwrite the first's output *before* `diff_impact()` read `model_dir_a` back from disk, making it always read the *b* (new) version under the *a* label. Every `measures_removed_impact`/`measures_modified_impact` entry's `used_by` came back empty regardless of real dependencies — a silent wrong-answer, not a crash, so nothing in the existing suite caught it (`test_cli_diff.py` only ever diffed a fixture against itself, where this bug and the correct answer are indistinguishable). Fixed: when `a_path`/`b_path` resolve to the same model name, `b`'s output is routed to a separate `_diff_b` subdirectory instead of colliding with `a`'s. No test previously exercised two *different* same-named models with a real broken dependency — that gap is what let this ship in the first place; `test_githooks_pbip_diff.py`'s end-to-end cases now cover it via the hook, and are the first tests in the repo to do so.

- **P1 follow-up to a general architecture/test-coverage/tech-debt audit** (`Pruebas/auditoria_general_2026-07-24.md`), four items:
  - **Error-handling inconsistency across input formats**: a corrupt table file under `.pbip`'s `tables/` used to raise `TmdlParseError` and abort the *entire* model, while `.pbit` already tolerated a bad row/table with a warning-and-continue (`processor.py`). `pbip_extractor.py`'s per-table-file loop now catches, warns (`print(f"Warning: ...")`, same idiom as `processor.py`), and skips instead of raising — the relationships file (`relationships.tmdl`/`model.tmdl`) is unchanged and still aborts on failure, since it isn't a per-item loop. New test: `test_error_corrupt_table_file_is_skipped_not_fatal`.
  - **"Flat measure" shape centralized**: `indexed_output._flat_measure`/`_MEASURE_FLAT_TOON_FIELDS` are now public (`flatten_measure`/`MEASURE_FLAT_FIELDS`) and `resolver.get_table()`'s JSON-path measure normalization calls `flatten_measure()` instead of re-declaring the same 6 keys inline — one source of truth instead of three, closing the exact drift pattern that caused the `partition_count` bug below. Also made `indexed_output._safe_filename` public (`safe_filename`) since `resolver.py` already imported it across the module boundary.
  - **`resolver._load_json()` now caches by (resolved path, mtime)**: `mcp_server.py` binds one long-lived process to one model directory and calls resolver functions repeatedly (list/search operations call `get_table()` once per table, every time) — every call used to re-read and re-parse the same JSON files from disk with no reuse *across* tool calls (the 2026-07-18 perf fix only deduplicated reads *within* a single transitive BFS call). Invalidates automatically on mtime change rather than caching forever, so reprocessing a model while a server is bound to it is picked up. New tests: `test_load_json_is_cached_across_calls`, `test_load_json_cache_invalidates_on_mtime_change`.
  - **TMDL parser (`_parse_table_tmdl_file`) hardening tests**: 4 new tests targeting mixed tab/space indentation isolation (a malformed column/measure block must not poison well-formed siblings in the same file) and arbitrarily deep DAX nesting (both the plain multi-line and backtick-fenced forms) beyond the shallow depths every existing fixture happened to use. All passed against the existing implementation unchanged — the parser was already more resilient here than the audit worried; this closes the coverage gap without needing a code fix.

- **`extractor.py` (.pbit path) had zero test coverage** and **`cli.py --batch` had no tests at all** — flagged as the top-priority findings of the same audit. Added `tests/test_extractor.py` (29 tests, in-memory zip fixtures built per-test — no `.pbit` fixture existed anywhere in the repo before) and `tests/test_cli_batch.py` (3 tests: no-match, all-succeed, partial-failure). Writing the extractor tests surfaced a real bug: `clean_json_text()`'s comment/trailing-comma regex substitutions used `r"\\1"` (literal backslash + "1") instead of `r"\1"` (group backreference), so cleaning a DataModelSchema containing `//`/`/* */` comments or trailing commas corrupted the JSON instead of fixing it, turning a recoverable parse into a `SchemaParseError`. Fixed in `extractor.py`.

- **`partition_count` never reached `index.json`/`tables/*.json`** — computed correctly in `processor.py`, but silently dropped by all three `indexed_output.py` table-entry builders and stripped again by `resolver.get_table()`'s field allowlist, making it invisible to the resolver and MCP server regardless of source format. Found via the answer-quality experiment above (a question about tables with zero partitions failed in every tested condition, one burning 12 function-calling round-trips trying to find it). Fixed across `indexed_output.py` and `resolver.py`; additive field with a safe default, no `index.json` version bump needed (see `docs/index-json-spec.md`).

Suite as of this release: 283 tests, all green.

### Docs

- `docs/scale_validation_report.md` section 5.2: real (not projected) measurement of the
  compact-JSON change on the 60-table synthetic model. Real token counts via the Anthropic API
  remain blocked in this environment (no `ANTHROPIC_API_KEY`) — figures are still bytes, not
  measured tokens.

### Considered, not implemented

- **`--skip-legacy` for `agent_context.json`/`model_context.jsonl`**: evaluated and deliberately
  left out of this release. Neither file is on the read path used by `resolver.py`/`mcp_server.py`
  — skipping them would save generation time/disk, not query-time tokens. See the comment in
  `cli.py` above the legacy-output block.

### Architecture

- Stable internal contract (`cleaned_metadata` dict) preserved — `processor.py`, `formatters.py`, `categorizer.py`, `documentation.py`, `jsonl_generator.py`, `diff.py`, `i18n.py` were not modified.
- Both extractors produce the same `raw_schema` shape, enabling `process_schema()` reuse without branching.

---

## [0.1.0] - 2025-01-XX

### Added
- **Modular project structure**: Complete refactoring of monolithic code into specialized modules
  - `extractor.py`: DataModelSchema extraction from .pbit files with robust validations
  - `processor.py`: Model processing with error handling and validations
  - `formatters.py`: Advanced DAX formatting with regex, tokenization and intelligent indentation
  - `categorizer.py`: Intelligent categorization of tables, columns and measures
  - `documentation.py`: Markdown documentation generation with formatted DAX and complexity
  - `diff.py`: Model comparison and diff generation
  - `cli.py`: Complete CLI with logging, validations and error handling
  - `jsonl_generator.py`: JSONL context generator for LLMs with optimized DAX

- **Advanced hierarchical DAX formatting**: Complete visual indentation system that reflects logical structure
  - Incremental indentation (+4 spaces) for each nesting level
  - Automatic alignment of closing parentheses with the start of their function
  - Arguments on separate lines for maximum readability
  - Recognition of complex functions: `CALCULATE`, `FILTER`, `SUMX`, `AVERAGEX`, `DIVIDE`, `TOTALYTD`, `TOTALQTD`, `TOTALMTD`, `SAMEPERIODLASTYEAR`, `DATESYTD`
  - Intelligent tokenization with recognition of functions, operators and columns
  - Complexity categorization (simple/medium/complex) with automatic scoring
  - Specific formatting for Markdown and JSON with appropriate escaping
  - Visual complexity indicators in documentation (Simple/Medium/Complex)

- **Robust validations and error handling**: Complete validation and logging system
  - Input file validation (valid .pbit files, non-empty, existing)
  - Schema structure validation (required keys, correct types)
  - Specific error handling with custom exceptions
  - Configurable logging system with levels (INFO/DEBUG)
  - Warnings for problematic elements without interrupting processing

- **JSONL generator for LLMs**: Format optimized for embeddings and RAG
  - Context per table with columns and example prompts
  - Context per measure with formatted DAX expressions
  - Context per relationship with cardinality and filtering
  - General model context with executive summary

- **Enhanced CLI with multiple modes**:
  - `--input/-i`: Individual file processing
  - `--output/-o`: Customizable base output directory
  - `--batch`: Batch processing with glob patterns
  - `--diff`: Comparison between two models with JSON diff generation
  - `--lang` / `--language`: Multi-language support (English/Spanish) for documentation generation

- **Professional Python packaging**:
  - `pyproject.toml` with complete project metadata
  - Console entry point: `pbi-docs`
  - Editable installation: `pip install -e .`
  - Package structure: `pbi_extractor/`

- **Cross-platform paths**: Complete migration to `pathlib.Path`
  - Removal of Windows-specific paths (`r"data\..."`)
  - Native support for Windows, Linux and macOS

- **Intelligent measure categorization**:
  - Revenue, Cost, Margin, Percentage, Ratio
  - Temporal, Calendar Intelligence, Aggregation
  - Filtering and Other

- **Multi-language support**: Generate documentation in English (`--lang en`) or Spanish (`--lang es`). English is the default language.
  - New CLI flag `--lang` or `--language` to select documentation language
  - All documentation strings (headers, labels, category names, complexity indicators) are translated
  - `model_documentation.md` and `agent_context.json` are generated in the selected language
  - New `i18n.py` module with translation dictionaries for English and Spanish
  - Complete translation coverage for all user-facing strings

- **Improved automatic documentation**:
  - Structured Markdown with tables and DAX code
  - Measure grouping by category with icons
  - Usage guide for AI agents
  - JSON context for APIs and integrations

- **Robust DataModelSchema parsing**:
  - Automatic fallback to search for "DataModelSchema", "DataModel" or "model.json"
  - Support for different naming conventions in .pbit files
  - Better handling of non-standard schemas

### Changed
- **Project renaming**: Complete migration from "ConectorBI" to "pbi-docs"
  - CLI command changed from `pbi-extractor` to `pbi-docs`
  - All documentation and references updated to reflect new project name
  - GitHub URLs and project metadata updated

- **Complete refactoring of DAX formatter** (`formatters.py`):
  - New `_format_dax_simple()` function with regex-based logic and indentation stack
  - New `_align_closing_parentheses()` function for precise parenthesis alignment
  - Improved `_is_complex_function_line()` to detect more nested functions
  - Clear separation between formatting for documentation and JSON
  - Stack-based indentation tracking for precise level handling
  - Robust regex for function and argument tokenization
  - Special handling of column references with brackets
  - Preservation of comments and string literals

- **File restriction**: Only support for `.pbit` (not `.pbix`)
  - Clear error with instructions to export from Power BI Desktop
  - Better handling of unsupported files

- **Output structure**: Organization by input file
  - `output/[file-name].pbit/metadata.json`
  - `output/[file-name].pbit/model_documentation.md`
  - `output/[file-name].pbit/agent_context.json`
  - `output/[file-name].pbit/model_context.jsonl`

- **Relative imports**: Complete migration to package imports
  - `from .module import function` instead of absolute imports
  - Better encapsulation and code organization

- **Improved generated documentation**:
  - DAX expressions now clearly show the hierarchy of nested functions
  - Each nesting level is visually distinguishable
  - Closing parentheses align with the start of their corresponding function

### Fixed
- **DAX argument preservation**: Critical fix where the first argument of complex functions was omitted during formatting
  - Previously: `CALCULATE( , SAMEPERIODLASTYEAR(...))` (incorrect)
  - Now: `CALCULATE( [YTD Gross Margin], SAMEPERIODLASTYEAR(...))` (correct)
  
- **Flat indentation**: Fixed indentation levels that did not reflect logical hierarchy
  - All internal arguments now increase their indentation according to nesting depth
  - Closing parentheses maintain visual consistency with their opening

- **Encoding handling**: Robust support for UTF-8, UTF-16 and Latin-1
- **JSON parsing**: Automatic cleanup of comments and trailing commas
- **Column categorization**: Better detection of types and categories

### Testing
- **Test suite**: Unit tests for categorizer, processor, and internationalization modules using pytest
  - Tests for technical table detection (`test_categorizer.py`)
  - Tests for schema processing and context generation (`test_processor_and_context.py`)
  - Tests for internationalization module (`test_i18n.py`)
  - Test coverage for measure categorization and column category detection
  - Tests for translation functions (`get_translation`, `get_category_name`, `get_complexity_label`)
  - Tests for translation completeness and non-empty translations
  - Tests for Spanish language support in documentation generation
- **Testing framework**: pytest >= 7.0.0 configured in `requirements-dev.txt`

### Documentation
- **Complete README.md**: Installation, usage and examples guide
  - All content translated to English
  - All emojis replaced with descriptive text
  - Added reference to Microsoft Power BI Desktop Samples repository
  - Updated examples to use "Life expectancy v202009" sample file
  - New "DAX Formatting Example" section with before/after comparison
  - Updated features table with "Advanced DAX Formatting"
  - Improved comparison table with "Advanced DAX formatting" column
  - Updated CLI and usage instructions
  - JSONL output examples for LLM integration
- **Project badges**: Python version, License, Platform
- **Comparison section**: With Tabular Editor, DAX Studio, Power BI Desktop
- **Use cases**: Automatic documentation, onboarding, auditing, AI integration
- **Contribution guide**: Development process and bug reporting
- **MIT License**: LICENSE file with terms of use
- **CHANGELOG.md**: Fully translated to English

### Architecture
- **Separation of concerns**: Each module with specific function
- **Clear interfaces**: Well-documented functions with type hints
- **Extensibility**: Structure prepared for future features
- **Testing ready**: Modular code facilitating unit tests
