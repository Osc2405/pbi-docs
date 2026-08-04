# `index.json` — open format specification

`index.json` is a small, stable contract meant to be consumed directly by any tool — not just
pbi-context' own CLI/resolver/MCP server. This section documents it so other parsers can be built
against it without reading `pbi_extractor` source.

By default, `index.json`, `tables/*.json`, and `relationships.json` are written **compact** (no
indentation) — these files are meant for machine/LLM consumption via the resolver/MCP server, not
for a human reading raw JSON (`model_documentation.md` is the human-readable artifact). Pass
`--pretty` to restore indented JSON for debugging.

## Top-level shape

```jsonc
{
  "version": "1",                 // bump on any incompatible shape change
  "model_name": "Sales Sample",
  "extraction_date": "2026-07-16T12:10:36.023218",
  "compatibility_level": "1601",  // Analysis Services compatibility level, as a string
  "source_format": "pbip",        // "pbit" | "pbip"
  "index_format": "auto",         // "json" | "toon" | "auto" — see per-table "format" below
  "summary": { "total_tables": 11, "total_columns": 81, "total_measures": 29, "total_relationships": 5, ... },
  "tables": [ /* one entry per table, see below */ ],
  "files": {
    "metadata": "metadata.json",
    "documentation": "model_documentation.md",
    "agent_context": "agent_context.json",
    "model_context": "model_context.jsonl",
    "relationships": "relationships.json"
  }
}
```

## Per-table entry (`tables[]`)

```jsonc
{
  "name": "Calendar",
  "is_hidden": false,
  "is_technical": false,          // heuristic flag for date-template/helper tables
  "partition_count": 1,           // number of physical partitions defined for this table
  "column_count": 29,
  "measure_count": 0,
  "categories": ["revenue", "cost"],   // distinct measure categories present in this table (empty if none)
  "format": "toon",               // "json" | "toon" — the ACTUAL format of this table's file.
                                   // Always trust this field, not the top-level "index_format":
                                   // under "auto" mode each table decides independently based on
                                   // its own size (see below), so different tables in the same
                                   // model can legitimately have different values here.
  "path": "tables/Calendar.json"  // relative to index.json's own directory
}
```

**Why per-table `format` can vary:** `--index-format auto` picks JSON or TOON per table based on
`len(columns) + len(measures)` — TOON's `{__toon, __fields, __rows}` wrapper only pays for itself
once a table is large/uniform enough to amortize it (empirically confirmed on
`files_test/Supply Chain Sample.pbip`: 5 rows still loses to JSON, 7 rows already wins — see
`docs/token_optimization_report.md` section 4). A consumer must read `format` per table and never
assume the whole model shares one encoding.

## `tables/<Name>.json` contract

Two possible shapes, selected by that table's `format`:

**`"format": "json"`** — plain, human-readable:
```json
{
  "name": "About",
  "is_hidden": false,
  "is_technical": false,
  "partition_count": 1,
  "columns": [
    {"name": "Key", "data_type": "string", "category": "identifier", "is_hidden": false,
     "source_column": "Key", "format_string": ""}
  ],
  "measures": [
    {"name": "# Customers", "expression": "COUNTROWS('Customer')",
     "formatted_expression": "COUNTROWS('Customer')", "format_string": "#,##0",
     "is_hidden": false, "display_folder": "", "category": "other"}
  ]
}
```

**`"format": "toon"`** — columns and a flat measure summary use TOON encoding
(`{__toon, __fields, __rows}`, a header + row-array shape — see `pbi_extractor/toon_encoder.py`),
DAX bodies stay in a separate plain-JSON list so free-text expressions are never TOON-encoded.
`partition_count` is likewise never TOON-encoded — it's a per-table scalar, not a tabular array,
so it stays a plain top-level key in both formats, same treatment as `is_hidden`/`is_technical`:
```json
{
  "name": "Calendar",
  "is_hidden": false,
  "is_technical": false,
  "partition_count": 1,
  "columns": {
    "__toon": true,
    "__fields": ["name", "data_type", "category", "is_hidden", "source_column", "format_string"],
    "__rows": [["Date", "dateTime", "temporal", false, "Date", "yyyy-mm-dd"], ...]
  },
  "measures_flat": {
    "__toon": true,
    "__fields": ["name", "category", "complexity", "is_hidden", "format_string", "display_folder"],
    "__rows": [...]
  },
  "measures_dax": [
    {"name": "Sales Amount", "formatted_expression": "SUMX('Sales',\n    'Sales'[Quantity] * 'Sales'[Net Price])"}
  ]
}
```

A consumer that wants one uniform shape regardless of format should decode TOON blocks
(`__fields`/`__rows` → list of dicts by zipping) and merge `measures_flat` + `measures_dax` by
`name` — exactly what `pbi_extractor/resolver.py`'s `get_table()` does; read that function if you
want a reference implementation in ~30 lines.

## Versioning

`version: "1"` today. Any change that breaks a consumer reading the shapes above (renaming a
field, changing `tables[]` entry keys, changing what `format`/`index_format` can contain) must
bump this value. Additive changes (a new optional field) don't require a bump.

## Formal schema

The shape above is also captured as a JSON Schema (draft 2020-12):
[`docs/index.schema.json`](index.schema.json). It covers `index.json` only, not `tables/*.json` or
`relationships.json` (both of which vary shape based on TOON vs. plain JSON — `index.json` itself
never does). `tests/test_indexed_output.py` validates real `build_index()` output against it, so
the schema can't silently drift from the actual generated shape.
