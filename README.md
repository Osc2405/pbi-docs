## pbi-docs — AI Context Engine for Power BI Models


[![Tests](https://github.com/Osc2405/pbi-docs/actions/workflows/tests.yml/badge.svg)](https://github.com/Osc2405/pbi-docs/actions/workflows/tests.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/Osc2405/pbi-docs/actions/workflows/tests.yml)

**Compiles Power BI models (`.pbit` and `.pbip`/TMDL) into indexed, queryable context for AI
agents — via files, CLI (`--query`), or a built-in MCP server. Human-readable documentation is
one of several outputs, not the whole story.**

Automatically extract metadata from Power BI models and generate:
- **Indexed, queryable context for AI agents** — `index.json` + per-table files, on-demand lookup/search (`--query`), a read-only **MCP server** (`--mcp-serve`), and chat-invocable **Skills** for Claude Code / Copilot
- AI-optimized JSON/JSONL context for LLMs and RAG pipelines
- Human-readable Markdown documentation
- Categorized measures (revenue, cost, margin, etc.)
- **Hierarchical DAX formatting** for maximum readability

No external dependencies. Python-only — including the MCP server, hand-rolled against the stable JSON-RPC spec rather than pulling in the official SDK's dependency tree.

## Why pbi-docs?

| Your Need | pbi-docs Solution |
|-----------|---------------------|
| **Document 10+ dashboards fast** | Batch processing with `--batch` |
| **Support new PBIP format** | Full TMDL parser, auto-detected from `.pbip` or folder |
| **Train AI agents on your models** | AI-optimized JSONL + indexed output |
| **Actually readable DAX** | Hierarchical indentation (4x better than raw) |
| **Zero-cost, zero-install** | Python-only, no .NET dependencies |
| **Compare model versions** | Built-in `--diff` mode (mixed formats supported) |

**Perfect for:** Data engineers onboarding teams, consultants auditing models, organizations building AI copilots for BI.


## Quick Start

```powershell
# 1. Clone the repository
git clone https://github.com/Osc2405/pbi-docs.git
cd pbi-docs

# 2. Install the package
pip install -e .

# 3a. Generate documentation from a .pbit file
pbi-docs --input "data/pbit/my-model.pbit"

# 3b. Or from a PBIP project folder (new in v1.0)
pbi-docs --input "data/pbip/my-model/"

# 4. Review the results (Windows PowerShell)
Get-Content "output/my-model.pbit/model_documentation.md"
```

**Result:** Complete documentation of your Power BI model in seconds. 7 files are generated per model (4 original + `index.json`, `relationships.json`, and per-table JSON files).

## Demo

### Input (Power BI Model)
![Power BI Model](docs/images/powerbi-sample.png)

### CLI Usage
![CLI Usage](docs/images/CLI_Usage.png)

### AI Agent Using the Documentation
![ChatGPT Demo](docs/images/ChatGPT-demo.gif)

---

## Minimal Reproducible Example

> **Note:** The sample files used in this documentation are available from the [Microsoft Power BI Desktop Samples repository](https://github.com/microsoft/powerbi-desktop-samples). These are official sample files provided by Microsoft for learning and testing purposes.

### Step 1: Prepare a .pbit file

If you have a `.pbix` file, export it to `.pbit` from Power BI Desktop:
1. Open your `.pbix` file in Power BI Desktop
2. Go to **File > Export > Power BI Template**
3. Save the `.pbit` file in the `data/pbit/` folder

Alternatively, you can download sample `.pbit` files from the [Microsoft Power BI Desktop Samples repository](https://github.com/microsoft/powerbi-desktop-samples) and export them to `.pbit` format.

### Step 2: Run the extractor

```powershell
# Process your .pbit file
pbi-docs --input "data/pbit/my-model.pbit"
```

### Step 3: Verify the output

The command generates a folder in `output/` with all documentation files:

```
output/my-model.pbit/          (or output/my-model/ for PBIP)
├── metadata.json              # Structured model metadata
├── model_documentation.md     # Human-readable documentation
├── agent_context.json         # LLM-optimized context (top-20 measures)
├── model_context.jsonl        # JSONL format for embeddings/RAG
├── index.json                 # Lightweight index + pointers (NEW)
├── relationships.json         # All relationships (NEW)
└── tables/
    ├── Sales.json             # Full detail per table (NEW)
    └── ...
```

### Step 4: Review the documentation

**Expected output example:**

```powershell
# View the model summary
Get-Content "output/my-model.pbit/model_documentation.md" | Select-Object -First 15
```

**Output:**
```markdown
# my-model - Power BI Data Model

**Generated:** 2025-12-22 14:23:29

## Model Summary

- **Business Tables:** 9
- **Total Columns:** 23
- **Total Measures:** 44
- **Relationships:** 9
```

### Step 5: Use the context for AI

```python
import json

# Load context for AI analysis
with open("output/my-model.pbit/agent_context.json", "r", encoding="utf-8") as f:
    context = json.load(f)
    
print(f"Model: {context['model_name']}")
print(f"Key measures: {len(context['key_measures'])}")
print(f"First measure: {context['key_measures'][0]['name']}")
```

**Expected output:**
```
Model: my-model
Key measures: 20
First measure: Revenue Budget
```

---

## Project Status

- **Implemented (see `CHANGELOG.md` for full detail)**
  - CLI `pbi-docs` with modes: single file (`--input/-i`), custom output (`--output/-o`), batch (`--batch`), model diff (`--diff`), on-demand query (`--query`), and MCP server (`--mcp-serve`), plus verbose mode (`--verbose`).
  - **`.pbit` and `.pbip`/TMDL support**, auto-detected from file extension or folder structure — hand-rolled parsers for both, zero external dependencies.
  - **Multi-language support**: Generate documentation in English (`--lang en`) or Spanish (`--lang es`). English is the default.
  - Model processing and generation of `metadata.json`, `model_documentation.md`, `agent_context.json`, `model_context.jsonl`, plus indexed output (`index.json`, `tables/*.json`, `relationships.json`) in `json` or `toon` format (`--index-format`).
  - **Query resolver** (`pbi_extractor/resolver.py`) — structured on-demand access to a processed model (`list_tables`, `get_table`, `get_measure`, `search_measures`, `search_columns`, `get_relationships`), normalizing JSON vs TOON transparently. Exposed via `--query` and as 6 MCP tools.
  - **Read-only MCP server** (`pbi_extractor/mcp_server.py`) — hand-rolled stdio JSON-RPC, no `mcp` SDK dependency.
  - **Chat-invocable Skills** for Claude Code (`.claude/skills/analyze-pbi-model/`) and GitHub Copilot (`.github/prompts/analyze-pbi-model.prompt.md`).
  - Advanced DAX formatting with hierarchical indentation and complexity classification (Simple/Medium/Complex).
  - Intelligent measure categorization (revenue, cost, margin, percentage, ratio, temporal, calendar, etc.).
  - Python packaging (`pyproject.toml`) with console entry point `pbi-docs`. **203 tests**, zero external dependencies.
  - Evidence-based reports backing the above claims, not just asserted: see [Reports](#reports) below.

- **Explicitly out of scope for now**
  - Writing/editing TMDL models (add/modify measures, columns, relationships) — a much larger undertaking (format preservation, validation, merge/conflict handling) than reading, and Microsoft's Modeling MCP already covers this space.
  - PBIR / report-layer parsing (pages, visuals, bookmarks) — a distinct problem from documenting the semantic model.
  - Native `.pbix` parsing (export to `.pbit` or `.pbip` first).

## Features

| Feature | Description |
|---------|-------------|
| **PBIP / TMDL Support** | Reads `.pbip` projects and `.SemanticModel/` folders (new in v1.0) |
| **Auto-detection** | Detects format automatically from file extension or folder structure |
| **Automatic Extraction** | Reads `.pbit` files without additional configuration |
| **Indexed Output** | Generates `index.json` + per-table JSON files for large-model navigation |
| **Query Resolver + `--query`** | On-demand table/measure/relationship lookup and search, no need to load whole files |
| **MCP Server** | `--mcp-serve` — read-only MCP server (stdio), no `mcp` SDK dependency |
| **Chat Skills** | Claude Code Skill + GitHub Copilot prompt file for analyzing a model from chat |
| **Advanced DAX Formatting** | Hierarchical indentation with parenthesis alignment for maximum readability |
| **Intelligent Categorization** | Automatically identifies revenue, cost, temporal columns |
| **Multi-language Support** | Generate documentation in English or Spanish via `--lang` flag |
| **Multi-format Docs** | Generates Markdown + JSON + JSONL + indexed output |
| **AI-Ready** | Context optimized for Claude, GPT, and other LLMs |
| **Zero Dependencies** | Standard Python only, no external libraries |

---

## Requirements
- Python 3.10+ (3.12 recommended)
- Windows PowerShell (instructions include Windows commands)

Optional: virtual environment (`venv`). No external libraries required.

---

## Installation (Windows/PowerShell)

```powershell
# 1) Clone or download the repository
# 2) (Optional) Create and activate virtual environment
python -m venv venv
./venv/Scripts/Activate.ps1

# 3) Editable installation (development)
pip install -e .

# Verify Python version
python --version
```

If PowerShell blocks activation, run as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

## Quick Usage

### Basic Commands

**Process a `.pbit` file:**
```powershell
pbi-docs --input "data/pbit/my-model.pbit"
```

**Process a PBIP project (new in v1.0):**
```powershell
# From the .pbip marker file
pbi-docs --input "data/pbip/my-model.pbip"

# From the .SemanticModel folder directly
pbi-docs --input "data/pbip/my-model.SemanticModel"

# From the project root folder (auto-detected)
pbi-docs --input "data/pbip/my-model/"
```

**Specify custom output directory:**
```powershell
pbi-docs -i "data/pbit/my-model.pbit" -o "my-results"
```

**Process multiple files (batch mode — mixed formats supported):**
```powershell
pbi-docs --batch "data/pbit/*.pbit"
```

![Batch Processing](docs/images/batch-processing.png)

**Compare two versions of a model (mixed `.pbit`/`.pbip` supported):**
```powershell
pbi-docs --diff "data/pbit/model_v1.pbit" "data/pbip/model_v2/"
```

**Verbose mode (more debugging information):**
```powershell
pbi-docs --input "data/pbit/my-model.pbit" --verbose
```

**Generate documentation in Spanish:**
```powershell
pbi-docs --input "data/pbit/my-model.pbit" --lang es
```

**Generate documentation in English (default):**
```powershell
pbi-docs --input "data/pbit/my-model.pbit" --lang en
# Or simply omit --lang (English is the default)
pbi-docs --input "data/pbit/my-model.pbit"
```

### Expected Output

When running the command, you'll see messages like:

```
Processing file: data/pbit/my-model.pbit
Schema extracted successfully: 11 tables
Metadata processed: 11 tables, 44 measures
Metadata saved to: output/my-model.pbit/metadata.json
Documentation saved to: output/my-model.pbit/model_documentation.md
Agent context saved to: output/my-model.pbit/agent_context.json
JSONL context saved to: output/my-model.pbit/model_context.jsonl
Processing completed successfully for: my-model.pbit
```

### Important Notes

- **Supported formats:** `.pbit` files (ZIP + JSON TMSL) and `.pbip` projects (TMDL folder structure). `.pbix` files must be exported to `.pbit` from Power BI Desktop (File > Export > Power BI Template).
- **PBIP entry points:** The `--input` flag accepts a `.pbip` marker file, a `.SemanticModel/` folder, or a project root folder. Format is auto-detected.
- **Language selection:** Use `--lang en` for English (default) or `--lang es` for Spanish. The language affects the generated `model_documentation.md` and `agent_context.json` files.
- **Paths with spaces:** Use quotes around paths that contain spaces.
- **Recommended paths:** Place your files in `data/` or `data/pbit/` to keep the project organized.

---

## Project Structure

```
pbi-docs/
├── pbi_extractor/           # Main package
│   ├── __init__.py
│   ├── cli.py              # CLI with argparse (auto-detection, --index-format)
│   ├── extractor.py        # .pbit (ZIP+JSON TMSL) extractor
│   ├── pbip_extractor.py   # .pbip / TMDL extractor (new in v1.0)
│   ├── processor.py        # Metadata processing (format-agnostic)
│   ├── indexed_output.py   # index.json + tables/*.json writer (new in v1.0)
│   ├── formatters.py       # Advanced hierarchical DAX formatting
│   ├── categorizer.py      # Table/measure categorization
│   ├── documentation.py    # Markdown generation
│   ├── diff.py             # Model comparison
│   ├── jsonl_generator.py  # JSONL generator for LLMs
│   └── i18n.py             # Translations (en/es)
├── tests/
│   ├── fixtures/
│   │   └── minimal_pbip/   # TMDL test fixtures (new in v1.0)
│   ├── test_pbip_extractor.py
│   ├── test_cli_detection.py
│   ├── test_indexed_output.py
│   ├── test_categorizer.py
│   ├── test_i18n.py
│   └── test_processor_and_context.py
├── data/                   # Input model files
├── output/                 # Generated results
├── pyproject.toml          # Package configuration
├── README.md
├── CHANGELOG.md
└── LICENSE
```

---

## Generated Outputs

After running the command, a folder is created in `output/` with the model name. Inside you'll find:

- **`metadata.json`**
  - `summary`: totals of tables, visible columns, visible measures and relationships.
  - `tables`: each table with `columns` (type, visibility, category) and `measures` (clean expression, format, display folder, category).
  - `relationships`: from/to, cardinality, direction and active status.

- **`model_documentation.md`**
  - Model summary (language depends on `--lang` flag, default: English).
  - List of tables (hidden or business), visible columns and measures grouped by category: revenue, cost, margin, percentage, ratio, temporal, etc.
  - Sections with DAX expressions formatted with **hierarchical indentation**.
  - Relationships table with visual representation of table connections.
  - AI Agent Usage Guide with sample questions (translated based on selected language).

![Model Relationships](docs/images/Relationships.png)

- **`agent_context.json`**
  - Model name, totals, available tables, key measures (up to 20), temporal columns and sample questions (language depends on `--lang` flag, default: English).

- **`model_context.jsonl`**
  - Line-delimited JSON format optimized for embeddings and RAG.
  - Each line is an independent object (table, measure or relationship).
  - Includes formatted DAX and sample prompts.

- **`index.json`** *(new in v1.0)*
  - Lightweight model summary with per-table metadata (column/measure counts, categories) and relative paths to all other output files.
  - Allows LLM agents to navigate large models without loading the full `metadata.json`.

- **`relationships.json`** *(new in v1.0)*
  - All model relationships in a single focused file.

- **`tables/<TableName>.json`** *(new in v1.0)*
  - Full detail for one table (columns + measures including DAX).
  - One file per table, addressable via `index.json`.

---

## `index.json` — open format specification

`index.json` is a small, stable contract meant to be consumed directly by any tool — not just
pbi-docs' own CLI/resolver/MCP server. This section documents it so other parsers can be built
against it without reading `pbi_extractor` source.

### Top-level shape

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

### Per-table entry (`tables[]`)

```jsonc
{
  "name": "Calendar",
  "is_hidden": false,
  "is_technical": false,          // heuristic flag for date-template/helper tables
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

### `tables/<Name>.json` contract

Two possible shapes, selected by that table's `format`:

**`"format": "json"`** — plain, human-readable:
```json
{
  "name": "About",
  "is_hidden": false,
  "is_technical": false,
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
DAX bodies stay in a separate plain-JSON list so free-text expressions are never TOON-encoded:
```json
{
  "name": "Calendar",
  "is_hidden": false,
  "is_technical": false,
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

### Versioning

`version: "1"` today. Any change that breaks a consumer reading the shapes above (renaming a
field, changing `tables[]` entry keys, changing what `format`/`index_format` can contain) must
bump this value. Additive changes (a new optional field) don't require a bump.

---

## Use Cases

### 1. Automatic Dashboard Documentation

**Problem:** Your company has multiple undocumented Power BI dashboards. Analysts waste time searching for which measures to use and how tables are related.

**Solution:**
```powershell
# Process all dashboards in a folder (English documentation)
pbi-docs --batch "data/dashboards/*.pbit"

# Or generate Spanish documentation for all dashboards
pbi-docs --batch "data/dashboards/*.pbit" --lang es
```

![Batch Processing Example](docs/images/batch-processing.png)

**Result:**
- Each dashboard generates its own documentation in `output/[dashboard-name].pbit/`
- Documentation ready to share with the team
- Automatic identification of measures by category (revenue, cost, margin, etc.)

**Output example:**
```
output/
├── Sales Dashboard.pbit/
│   ├── model_documentation.md  # 23 documented measures
│   └── metadata.json
├── Finance Dashboard.pbit/
│   ├── model_documentation.md  # 31 documented measures
│   └── metadata.json
└── Operations Dashboard.pbit/
    ├── model_documentation.md  # 18 documented measures
    └── metadata.json
```

---

### 2. New Analyst Onboarding

**Problem:** New employees need weeks to understand Power BI model structure and which measures to use for each analysis.

**Solution:**
1. Generate the model documentation (in your preferred language):
```powershell
# English documentation (default)
pbi-docs --input "data/pbit/my-model.pbit"

# Spanish documentation
pbi-docs --input "data/pbit/my-model.pbit" --lang es
```

2. Upload the `model_documentation.md` file to your favorite AI agent (Claude, GPT-4, etc.)

3. The agent can answer questions like:
   - "What revenue measures are available?"
   - "How is Gross Margin calculated?"
   - "What tables are related to Customer?"

**Interaction example:**
```
User: What revenue measures does this model have?

Agent: The "my-model" model has 11 revenue measures:
- Total Revenue (simple): SUM([Revenue])
- YTD Revenue (simple): TOTALYTD(SUM([Revenue]),'Date'[Date])
- Revenue SPLY (medium): CALCULATE([Total Revenue],SAMEPERIODLASTYEAR('Date'[Date]))
- Revenue Budget (medium): CALCULATE([Total Revenue], FILTER(Scenario, Scenario[Scenario]="Budget"))
...
```

**Benefit:** Significant reduction in onboarding time by having immediate answers about the model structure.

---

### 3. Model Auditing

**Problem:** You need to compare two versions of the same dashboard to identify which measures or relationships changed between releases.

**Solution:**
```powershell
# Compare two versions of the model
pbi-docs --diff "data/pbit/dashboard_v1.pbit" "data/pbit/dashboard_v2.pbit"
```

**Result:** A `diff_dashboard_v1_vs_dashboard_v2.json` file is generated, content-aware — not just
which measures/columns/relationships were added or removed, but which existing ones changed
content (DAX expression, format string, display folder, hidden flag, category, data type,
cardinality, cross-filtering, active flag).

Identity for matching an object across both models:
- Measures and columns: `(table, name)`.
- Relationships: `(from_table, from_column, to_table, to_column)` — a relationship that keeps the
  same connected columns but changes cardinality/cross-filtering/active flag shows up in
  `relationships_modified`, not as a remove+add.

DAX changes are flagged `"semantic"` or `"cosmetic"` via a whitespace-insensitive comparison of
`formatted_expression` — this is a text heuristic (DAX has no whitespace-sensitive syntax, so a
pure reindent compares equal), not a DAX parser; a change to a comment or to non-functional
casing would still register as semantic.

**Output example (`diff_*.json`):**
```json
{
  "a_model": "dashboard_v1",
  "b_model": "dashboard_v2",
  "measures_added": [["Fact", "New Revenue Measure"]],
  "measures_removed": [["Fact", "Deprecated Measure"]],
  "measures_modified": [
    {
      "table": "Fact",
      "name": "Total Sales",
      "changes": {
        "formatted_expression": {"old": "SUM(Fact[Amount])", "new": "SUM(Fact[NetAmount])", "dax_change": "semantic"},
        "display_folder": {"old": "", "new": "Sales"}
      }
    }
  ],
  "columns_added": [],
  "columns_removed": [],
  "columns_modified": [
    {"table": "Fact", "name": "Amount", "changes": {"data_type": {"old": "int64", "new": "decimal"}}}
  ],
  "relationships_added": [],
  "relationships_removed": [],
  "relationships_modified": [
    {
      "from_table": "Fact", "from_column": "DateKey", "to_table": "Date", "to_column": "Date",
      "changes": {"cardinality": {"old": "many:one", "new": "one:one"}}
    }
  ]
}
```

---

### 4. Integration with AI Agents and RAG

**Problem:** You want to create a RAG (Retrieval-Augmented Generation) system that answers questions about your Power BI models using embeddings.

**Solution:**
```python
import json

# Load JSONL context to create embeddings
context_entries = []
with open("output/my-model.pbit/model_context.jsonl", "r", encoding="utf-8") as f:
    for line in f:
        entity = json.loads(line)
        context_entries.append(entity)

# Each entry is independent and ready for embeddings
for entry in context_entries:
    print(f"Type: {entry['type']}, Title: {entry['title']}")
    if entry['type'] == 'measure':
        print(f"  DAX Expression: {entry['formatted_expression']}")
        print(f"  Complexity: {entry['complexity']}")
```

**Output example:**
```
Type: model, Title: Model: my-model
Type: table, Title: Fact (Hidden)
Type: measure, Title: Total Revenue (revenue)
  DAX Expression: SUM([Revenue])
  Complexity: simple
Type: measure, Title: Revenue SPLY (revenue)
  DAX Expression: CALCULATE(
    [Total Revenue],
    SAMEPERIODLASTYEAR(
    'Date'[Date]))
  Complexity: medium
Type: relationship, Title: Relationship: Fact -> Date
```

**Usage with embeddings:**
- Each JSONL line can be converted to an embedding
- Enables semantic search of measures, tables and relationships
- Ideal for chatbots that answer questions about Power BI models

### 5. Analyzing a model from chat (Claude Code / GitHub Copilot)

**Problem:** You want to ask an AI coding assistant questions about a Power BI model without
manually running the CLI and pasting file contents into chat.

**Solution:** pbi-docs ships two chat-invocable skills that run the extractor and then query the
model on demand via `pbi-docs --query` (see below) instead of dumping whole files into context:

- **Claude Code:** `.claude/skills/analyze-pbi-model/` — copy this folder into your own project's
  `.claude/skills/` (or work from inside this repo), then ask `/analyze-pbi-model <path>` or just
  "analyze this Power BI model" / "what measures does this model have".
- **GitHub Copilot (VS Code):** `.github/prompts/analyze-pbi-model.prompt.md` — copy into your own
  project's `.github/prompts/`, then run `/analyze-pbi-model` in Copilot Chat.

Both follow the same rule: read `index.json` first (it's tiny), then `--query` for anything
scoped to one table, a search, or relationships, and reach for `metadata.json` (the full
unfiltered dump) only as a last resort.

### 6. Querying a processed model (`--query`)

**Problem:** An agent (or script) needs one table's measures, or "which tables have a revenue
measure", without loading `metadata.json` or hand-parsing `tables/*.json` — and without caring
whether the output was generated as `--index-format json` or `toon`.

**Solution:** `pbi_extractor/resolver.py` normalizes both formats into one shape, exposed via
`--query`:

```bash
pbi-docs --query output/my-model --list-tables                                 # table summaries
pbi-docs --query output/my-model --list-tables --category revenue              # filtered
pbi-docs --query output/my-model --table "Sales"                               # one table, full detail
pbi-docs --query output/my-model --table "Sales" --measure "Total Sales"       # one measure, full record
pbi-docs --query output/my-model --search-measures "revenue"                   # cross-table measure search
pbi-docs --query output/my-model --search-columns "customer"                   # cross-table column search
pbi-docs --query output/my-model --relationships --table "Sales"               # relationships touching a table
```

Each prints JSON to stdout. This is the same query layer the two Skills above use, and what the
MCP server below wraps.

### 7. MCP server (`--mcp-serve`)

**Problem:** You want any MCP-capable client (Claude Desktop, Claude Code, Copilot, etc.) to
query a Power BI model directly as tools, not through a Skill's file-reading instructions.

**Solution:** `pbi_extractor/mcp_server.py` — a read-only MCP server, hand-rolled against the
stable spec (`2025-06-18`, newline-delimited JSON-RPC 2.0 over stdio). No `mcp` SDK dependency:
that package pulls in pydantic/anyio/httpx/starlette/uvicorn, which would break this project's
zero-dependency stance. One server instance is bound to one already-processed model directory,
exposing 6 tools — thin wrappers around `resolver.py`: `list_tables`, `get_table`, `get_measure`,
`search_measures`, `search_columns`, `get_relationships`.

```bash
pbi-docs --mcp-serve output/my-model
```

Configure it in your client's MCP settings (e.g. `claude_desktop_config.json` or Claude Code's
`.mcp.json`):

```json
{
  "mcpServers": {
    "pbi-docs": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "pbi_extractor.mcp_server", "output/my-model"]
    }
  }
}
```

To analyze a different model, point another server entry at a different `output/<model-name>`
directory — each instance is rooted to one model, same pattern as the filesystem MCP server.

This is deliberately read-only (no DAX execution, no model editing) — it's a context layer,
complementary to Microsoft's Modeling MCP (writes) and Remote MCP (executes DAX), not a
replacement for either.

**This repo ships its own `.mcp.json`** (project root) pointing at the `Supply Chain Sample`
validation fixture — a dev/demo convenience for testing `mcp_server.py` itself against a real
MCP client, not a template end users need (real usage is the config above, pointed at your own
processed model). To verify it against Claude Code:

1. Process the fixture first: `pbi-docs -i "files_test/Supply Chain Sample.pbip" -o output`.
2. Restart/reload Claude Code in this project (or open a fresh session here) — project-scoped
   `.mcp.json` servers require a session (re)start to be picked up.
3. Run `/mcp` — `pbi-docs` shows as `⏸ Pending approval` the first time; approve it.
4. Run `/mcp` again — should show connected, 6 tools.
5. Ask something like *"what tables does this Power BI model have"* — Claude should call
   `mcp__pbi-docs__list_tables` directly (visible in the transcript), not read any file.

This last step is the one thing about the MCP server that automated tests
(`tests/test_mcp_server.py`) can't cover — they prove protocol correctness against a harness I
wrote myself, not that a real client actually discovers and calls the tools.

---

## Reports

Every efficiency/correctness claim in this README is backed by a dated, reproducible report
against the real `Supply Chain Sample.pbip` fixture (not a synthetic toy model) — read these
before taking "AI-ready" or "token-optimized" at face value:

- **[docs/pbip_validation_report.md](docs/pbip_validation_report.md)** — end-to-end validation of
  PBIP/TMDL extraction and both output formats against a real (non-synthetic) export; documents
  5 bugs found and fixed in the process.
- **[docs/token_optimization_report.md](docs/token_optimization_report.md)** — measured token
  cost of raw TMDL vs pbi-docs JSON vs TOON across 3 usage scenarios, plus a table-by-table
  breakdown showing TOON is *not* a uniform win (loses on small tables).
- **[docs/precision_validation_report.md](docs/precision_validation_report.md)** — automated
  proxy for the "does scoped context sacrifice accuracy?" question: 3 isolated agents answer 18
  objectively-gradable questions using only raw TMDL / only JSON / only `--query`. JSON and
  `--query` both scored 18/18; raw TMDL scored 16/18 (the 2 misses were honest `NOT_FOUND` on a
  field TMDL doesn't contain at all, not agent error). Includes an honest caveat about total
  conversation token overhead vs. raw context-source bytes.

---

## DAX Formatting Example

The formatter now generates **hierarchical indentation** that reflects the logical structure of expressions:

![DAX Formatting](docs/images/DAX.png)

### Before (unformatted):
```dax
CALCULATE([YTD Gross Margin],SAMEPERIODLASTYEAR(DATESYTD('Date'[Date])))
```

### After (hierarchical formatting):
```dax
CALCULATE(
    [YTD Gross Margin],
    SAMEPERIODLASTYEAR(
        DATESYTD(
            'Date'[Date]
        )
    )
)
```

**Formatting features:**
- Each nesting level increases indentation (+4 spaces)
- Closing parentheses aligned with the start of their function
- Arguments on separate lines for clarity
- Preservation of all original arguments
- Complexity indicators (Simple / Medium / Complex)

---

## Troubleshooting

### Common Errors

**Error decoding `DataModelSchema`**: 
- The script tries `utf-8`, `utf-16` and `latin-1`, plus removes comments/trailing commas. 
- If it fails, `schema_snippet.txt` is saved in the output folder for diagnosis.

**Paths with spaces/special characters**: 
- Use quotes in the CLI: `pbi-docs -i "data/My File.pbit"`
- Prefer paths within `data/`.

**No documentation generated**: 
- Verify that the file contains `DataModelSchema`. 
- If you're using `.pbix`, export to `.pbit` from Power BI Desktop (File > Export > Power BI Template).

**PowerShell blocks venv activation**: 
- Adjust the `ExecutionPolicy` as indicated in installation.

### Verify Installation

Run a quick test with your .pbit file:

```powershell
pbi-docs --input "data/pbit/my-model.pbit"
```

**Expected output:**
```
Processing file: data/pbit/my-model.pbit
Schema extracted successfully: 11 tables
Metadata processed: 11 tables, 44 measures
Metadata saved to: output/my-model.pbit/metadata.json
Documentation saved to: output/my-model.pbit/model_documentation.md
Agent context saved to: output/my-model.pbit/agent_context.json
JSONL context saved to: output/my-model.pbit/model_context.jsonl
Processing completed successfully for: my-model.pbit
```

Then verify that the files were generated correctly:

```powershell
# List generated files
Get-ChildItem "output/my-model.pbit/"

# View a summary of the documentation
Get-Content "output/my-model.pbit/model_documentation.md" | Select-Object -First 10
```

### Common Installation Issues

**Error: "Python not recognized"**
```powershell
# Add Python to PATH or use full path
C:\Python312\python.exe -m pip install -e .
```

**Error: "No module named..."**
This project requires no dependencies. If you see this error, verify your Python version:
```powershell
python --version  # Must be 3.10+
```

**Error: "pbi-docs not recognized"**
```powershell
# Reinstall the package
pip install -e .
# Or use python -m
python -m pbi_extractor.cli --input file.pbit
```

---

## Comparison with Alternatives

| Feature | pbi-docs | Power BI Helper | Dataedo | Manual (DAX Studio) |
|---------|------------|-----------------|---------|---------------------|
| **Free & Open Source** | Yes | No (Paid) | No (Paid) | Yes |
| **Batch Processing** | Yes - Multiple files | No - One at a time | Yes | No |
| **Multi-language Support** | Yes - English & Spanish | No | No | No |
| **AI-Ready Outputs** | Yes - JSON + JSONL | No | Limited | No |
| **Hierarchical DAX** | Yes | Basic | Basic | No - Raw only |
| **No Installation** | Yes - pip install | Limited - Desktop app | Limited - Platform | Yes |
| **Categorization** | Yes - Auto (revenue, cost...) | No - Manual | Yes | No |
| **Version Diff** | Yes - Built-in | No | Yes | No - Manual |
| **MCP Server / On-demand Query** | Yes - Built-in, zero deps | No | No | No |

pbi-docs is a read/context-compilation layer, a different category from Microsoft's own Power BI
MCP servers (Modeling MCP for writes, Remote MCP for DAX execution) — complementary rather than
competing.

---

## Generated Documentation Example

<details>
<summary>View complete example of model_documentation.md (my-model)</summary>

```markdown
# my-model - Power BI Data Model

**Generated:** 2025-12-22 14:23:29

## Model Summary

- **Business Tables:** 9
- **Total Columns:** 23
- **Total Measures:** 44
- **Relationships:** 9

---

## Tables and Measures

### Fact *(Hidden Table - Measures Only)*

**Measures:**

##### Revenue Measures

**Total Revenue** *(simple)*

```dax
SUM([Revenue])
```

*Format:* `$#,0;($#,0);$#,0`

---

**YTD Revenue** *(simple)*

```dax
TOTALYTD(
    SUM([Revenue]),
    'Date'[Date])
```

*Format:* `$#,0;($#,0);$#,0`

---

**Revenue SPLY** *(medium)*

```dax
CALCULATE(
    [Total Revenue],
    SAMEPERIODLASTYEAR(
    'Date'[Date]))
```

*Format:* `$#,0;($#,0);$#,0`

##### Margin Measures

**Gross Margin** *(simple)*

```dax
[Total Revenue]-[Total COGS]
```

*Format:* `$#,0;($#,0);$#,0`

##### Percentage Measures

**GM%** *(simple)*

```dax
DIVIDE(
    [Gross Margin],
    [Total Revenue])
```

*Format:* `0.0 %;-0.0 %;0.0 %`

### Date

**Columns:**

| Column | Type | Category |
|--------|------|----------|
| `Date` | dateTime | temporal |
| `Year` | int64 | numeric |
| `Month` | string | categorical |

### Customer

**Columns:**

| Column | Type | Category |
|--------|------|----------|
| `Name` | string | descriptive |
| `City` | string | categorical |
| `State` | string | categorical |
| `Country/Region` | string | categorical |

## Relationships

| From | To | Type | Direction |
|------|----|----- |-----------|
| Fact.BU Key | BU.BU Key | many:one | OneDirection |
| Fact.YearPeriod | Date.YearPeriod | many:one | OneDirection |
| Fact.Customer Key | Customer.Customer | many:one | OneDirection |
```

</details>

---

## Contributing

Contributions are welcome! If you'd like to contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

**Bug reports and feature requests:** Please use [GitHub Issues](https://github.com/Osc2405/pbi-docs/issues)

---

## Roadmap

The read/context layer (PBIP/TMDL support, indexed output, query resolver, MCP server) is done.
Writing TMDL models and PBIR/report parsing are deliberately deferred — bigger undertakings, and
(for writing) Microsoft's own Modeling MCP already covers that space.

---

## Sample Files

The example files referenced in this documentation are official sample files provided by Microsoft. You can find these and other Power BI sample files in the [Microsoft Power BI Desktop Samples repository](https://github.com/microsoft/powerbi-desktop-samples).

These sample files are excellent for:
- Testing pbi-docs functionality
- Learning Power BI data modeling
- Exploring different DAX patterns and measure types
- Understanding relationship structures

To use these samples:
1. Clone or download the repository: `git clone https://github.com/microsoft/powerbi-desktop-samples.git`
2. Open the `.pbix` files in Power BI Desktop
3. Export them as `.pbit` files (File > Export > Power BI Template)
4. Use them with pbi-docs to generate documentation

---

## Author

**Oscar Rosero** - Data Engineer | BI Developer

-  [LinkedIn](https://www.linkedin.com/in/oscrosero24/)
-  [GitHub](https://github.com/Osc2405)
-  orosero2405@gmail.com

Built with ❤️ for the Power BI community.

---

## Star History

If this tool saves you time, please consider giving it a ⭐ on GitHub!


