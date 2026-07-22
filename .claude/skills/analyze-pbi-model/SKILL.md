---
name: analyze-pbi-model
description: Analyze a Power BI model (.pbit, .pbip, .SemanticModel folder, or project root) without leaving chat. Use when the user asks to explain, document, summarize, or answer questions about a Power BI/DAX model, its tables, measures, columns, or relationships — e.g. "analyze this pbit", "what measures does this model have", "explain this semantic model", "which tables relate to X".
argument-hint: [path-to-.pbit-or-.pbip-or-folder]
allowed-tools: Bash(pbi-docs *) Bash(python *) Bash(python3 *) Read Glob
---

# Analyze a Power BI model

Target model: `$ARGUMENTS`

If no path was given, ask the user for the `.pbit` file, `.pbip` file, `.SemanticModel/` folder,
or project root folder before doing anything else.

## Step 1 — Extract

Run the extractor once to generate the model's indexed output:

```
pbi-docs -i "$ARGUMENTS" -o output
```

If `pbi-docs` is not on PATH (not installed as a package), run it as a module from this skill's
repo root instead — `cli.py` uses relative imports, so it must run with `-m`, not as a bare script:

```
python -m pbi_extractor.cli -i "$ARGUMENTS" -o output
```

run with working directory `${CLAUDE_PROJECT_DIR}` (this skill's repo root), regardless of where
`$ARGUMENTS` itself points on disk.

Add `--lang es` for Spanish documentation, or `--index-format toon` when the model is large and
every token spent loading table/column/relationship listings matters.

The output lands in `output/<model-name>/`, where `<model-name>` is the input file's stem (for
`.pbit`) or the `.SemanticModel` folder's name without the suffix (for `.pbip`).

## Step 2 — Query, never load whole files speculatively

Use `pbi-docs --query output/<model-name> ...` (or `python -m pbi_extractor.cli --query ...` with
the same fallback rule as Step 1) instead of reading `tables/<Name>.json` or `relationships.json`
directly — the resolver already handles TOON decoding for you, so you never need to think about
`{__toon, __fields, __rows}` at all, regardless of which `--index-format` was used.

1. **Always start with `output/<model-name>/index.json`** (read the file directly, it's tiny). It
   has, per table: name, hidden/technical flags, column count, measure count, categories present.
   For "what's in this model" / "how many tables" questions, `index.json` alone is usually enough.
2. **For a specific table's columns/measures/DAX**, run
   `pbi-docs --query output/<model-name> --table "TableName"` — returns one JSON object with a
   unified `measures` list (name, category, complexity, format_string, display_folder,
   formatted_expression). Add nothing else; don't read the raw `tables/*.json` file yourself.
3. **For one specific measure once you already know the table and measure name**, run
   `pbi-docs --query output/<model-name> --table "TableName" --measure "MeasureName"` — cheaper
   than loading the whole table.
4. **For "which tables have X measures/columns" / "find the measure/column that does Y" questions**
   (something `index.json` alone can't answer — it would otherwise require opening every table
   file by hand), run `pbi-docs --query output/<model-name> --search-measures "keyword"` or
   `--search-columns "keyword"` (optionally `--category revenue` etc.).
5. **For relationship/join questions**, run
   `pbi-docs --query output/<model-name> --relationships [--table "TableName"]`.
6. **For a full human-readable narrative doc** (the user wants something to paste elsewhere, not
   an answer to a specific question), read `output/<model-name>/model_documentation.md` directly.
7. **`metadata.json`** is the complete, unfiltered dump (every table, every column, every DAX
   expression). Only read it directly if the question genuinely spans the whole model and
   `index.json` + a couple of `--query` calls aren't enough — it's the heaviest file in the output.

An MCP server (`--mcp-serve`) also exposes these same 6 capabilities as tools
(`list_tables`, `get_table`, `get_measure`, `search_measures`, `search_columns`,
`get_relationships`) for MCP-capable clients — see README.md section 7 if you'd rather configure
that instead of shelling out to `--query`.

## Step 3 — Answer

Answer the user's question using only what you loaded in Step 2, citing table and measure names
exactly as they appear in the source. Don't guess at DAX semantics beyond what's in
`formatted_expression` — quote it if precision matters.
