# pbi-context — AI Context Engine for Power BI Models

[![PyPI](https://img.shields.io/pypi/v/pbi-context)](https://pypi.org/project/pbi-context/)
[![Tests](https://github.com/Osc2405/pbi-context/actions/workflows/tests.yml/badge.svg)](https://github.com/Osc2405/pbi-context/actions/workflows/tests.yml)
[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/Osc2405/pbi-context/blob/main/LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)](https://github.com/Osc2405/pbi-context/actions/workflows/tests.yml)

**pbi-context is the zero-dependency context compiler that lets any AI agent read, query, and audit
a Power BI model** — via CLI, indexed JSON, or a read-only MCP server.

**Who it's for:** data engineers documenting dashboards, consultants auditing models they didn't
build, and anyone connecting an AI agent (Claude, GPT, Copilot) to a Power BI model's structure.

## Quick Start

```bash
pip install pbi-context

# From a .pbit file...
pbi-context --input "data/pbit/my-model.pbit"
# ...or a PBIP project (folder, .pbip marker, or .SemanticModel/ — auto-detected)
pbi-context --input "data/pbip/my-model/"

cat "output/my-model.pbit/model_documentation.md"
```

**Result:** 7 files in `output/<model-name>/` in seconds — human-readable Markdown, JSON/JSONL
context for AI agents, and an indexed, queryable version for large models.

<details>
<summary><strong>Full walkthrough</strong> — folder structure, expected output, and using the context in Python</summary>

The command generates a folder in `output/` with all documentation files:

```
output/my-model.pbit/          (or output/my-model/ for PBIP)
├── metadata.json              # Structured model metadata
├── model_documentation.md     # Human-readable documentation
├── agent_context.json         # LLM-optimized context (top-20 measures)
├── model_context.jsonl        # JSONL format for embeddings/RAG
├── index.json                 # Lightweight index + pointers
├── relationships.json         # All relationships
└── tables/
    ├── Sales.json             # Full detail per table
    └── ...
```

```bash
cat "output/my-model.pbit/model_documentation.md" | head -n 15
```
```markdown
# my-model - Power BI Data Model

**Generated:** 2025-12-22 14:23:29

## Model Summary

- **Business Tables:** 9
- **Total Columns:** 23
- **Total Measures:** 44
- **Relationships:** 9
```

Use the JSON context directly in Python (or point an AI agent at it via `--query` or
`--mcp-serve` — see [Use Cases](#use-cases) below):

```python
import json

with open("output/my-model.pbit/agent_context.json", "r", encoding="utf-8") as f:
    context = json.load(f)

print(f"Model: {context['model_name']}")
print(f"Key measures: {len(context['key_measures'])}")
print(f"First measure: {context['key_measures'][0]['name']}")
```
```
Model: my-model
Key measures: 20
First measure: Revenue Budget
```

</details>

## Why pbi-context?

| Your Need | pbi-context Solution |
|-----------|---------------------|
| **Document 10+ dashboards fast** | Batch processing with `--batch` |
| **Support the new PBIP format** | Full TMDL parser, auto-detected from `.pbip` or folder |
| **Train AI agents on your models** | Indexed JSON/JSONL context, a query CLI, and an MCP server |
| **Let an AI agent query the model live** | Read-only MCP server (`--mcp-serve`) — validated against a test harness, not yet a live MCP client, see [MCP server](https://github.com/Osc2405/pbi-context/blob/main/docs/use-cases.md#7-mcp-server---mcp-serve) |
| **Use it from your AI coding assistant** | Chat-invocable Skill for Claude Code + prompt file for GitHub Copilot |
| **Actually readable DAX** | Hierarchical indentation (4x better than raw) |
| **Compare model versions** | Content-aware `--diff`, with impact analysis (`--diff-impact`) |
| **See the model at a glance** | Embedded Mermaid ER diagram in `model_documentation.md` — renders natively on GitHub/VS Code |
| **Visualize the model in Gephi/yEd** | `--export-graph` — JSON node/edge lists or GraphML |
| **Zero-cost, zero-install** | Python-only, no .NET dependencies |

**Perfect for:** Data engineers onboarding teams, consultants auditing models, organizations building AI copilots for BI.

## Project Status

**v1.1.0 is published on [PyPI](https://pypi.org/project/pbi-context/)** under the name
`pbi-context` — this project was previously published as `pbi-docs` (v1.0.0–1.0.1); the tool
didn't change, only the name, to avoid a discoverability collision with an unrelated,
similarly-named project. See [CHANGELOG.md](https://github.com/Osc2405/pbi-context/blob/main/CHANGELOG.md)
for the full rename note.

The read/context layer — PBIP/TMDL support, indexed output, query resolver, MCP server,
`--diff-impact`, `--export-graph` — is done, implemented and tested (see the Tests badge above for
the current count). Every claim above is backed by a dated, reproducible report, not just
asserted: see [Validation](#validation) below.

**Next up:** validating with real human users that scoped context doesn't cost time or accuracy
versus raw file dumps — the protocol is ready
([docs/human_validation_protocol.md](https://github.com/Osc2405/pbi-context/blob/main/docs/human_validation_protocol.md)),
currently blocked on recruiting participants, not on code.

Writing/editing TMDL models and PBIR/report-layer parsing remain deliberately out of scope (see
[Roadmap](#roadmap) for why).

*Last updated: 2026-08-03.*

## Requirements
- Python 3.10+ (3.12 recommended)
- Works on Windows, macOS, and Linux

Optional: virtual environment (`venv`). No external libraries required.

## Installation

Just want to run `pbi-context`? `pip install pbi-context` (see Quick Start above) is all you need. The
steps below are for working on `pbi-context` itself (editable install from a local clone).

```bash
# 1) Clone or download the repository
# 2) (Optional) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate

# 3) Editable installation (development)
pip install -e .

# Verify Python version
python --version
```

<details>
<summary>Windows/PowerShell notes</summary>

```powershell
python -m venv venv
./venv/Scripts/Activate.ps1
```

If PowerShell blocks activation, run as Administrator:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

</details>

---

## Quick Usage

### Basic Commands

**Process a `.pbit` file:**
```bash
pbi-context --input "data/pbit/my-model.pbit"
```

**Process a PBIP project (new in v1.0):**
```bash
# From the .pbip marker file
pbi-context --input "data/pbip/my-model.pbip"

# From the .SemanticModel folder directly
pbi-context --input "data/pbip/my-model.SemanticModel"

# From the project root folder (auto-detected)
pbi-context --input "data/pbip/my-model/"
```

**Specify custom output directory:**
```bash
pbi-context -i "data/pbit/my-model.pbit" -o "my-results"
```

**Process multiple files (batch mode — mixed formats supported):**
```bash
pbi-context --batch "data/pbit/*.pbit"
```

**Compare two versions of a model (mixed `.pbit`/`.pbip` supported):**
```bash
pbi-context --diff "data/pbit/model_v1.pbit" "data/pbip/model_v2/"
```

**Verbose mode (more debugging information):**
```bash
pbi-context --input "data/pbit/my-model.pbit" --verbose
```

**Human-readable indexed output (indented JSON, for debugging — compact by default):**
```bash
pbi-context --input "data/pbit/my-model.pbit" --pretty
```

**Generate documentation in Spanish:**
```bash
pbi-context --input "data/pbit/my-model.pbit" --lang es
```

**Generate documentation in English (default):**
```bash
pbi-context --input "data/pbit/my-model.pbit" --lang en
# Or simply omit --lang (English is the default)
pbi-context --input "data/pbit/my-model.pbit"
```

See [docs/troubleshooting.md](https://github.com/Osc2405/pbi-context/blob/main/docs/troubleshooting.md)
for the full expected-output walkthrough, how to verify a fresh install, and common errors.

### Important Notes

- **Supported formats:** `.pbit` files (ZIP + JSON TMSL) and `.pbip` projects (TMDL folder structure). `.pbix` files must be exported to `.pbit` from Power BI Desktop (File > Export > Power BI Template).
- **PBIP entry points:** The `--input` flag accepts a `.pbip` marker file, a `.SemanticModel/` folder, or a project root folder. Format is auto-detected.
- **Microsoft Fabric semantic models:** Fabric uses the same TMDL format as PBIP, so compatibility is *expected* but **not empirically validated** (no real Fabric export has been tested against this parser yet) — see [docs/fabric_compatibility.md](https://github.com/Osc2405/pbi-context/blob/main/docs/fabric_compatibility.md).
- **Language selection:** Use `--lang en` for English (default) or `--lang es` for Spanish. The language affects the generated `model_documentation.md` and `agent_context.json` files.
- **Paths with spaces:** Use quotes around paths that contain spaces.
- **Recommended paths:** Place your files in `data/` or `data/pbit/` to keep the project organized.

---

## Project Structure

```
pbi-context/
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
├── githooks/                # Reference pre-commit hook (docs/pre_commit_hook.md)
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
pbi-context' own CLI/resolver/MCP server: a lightweight per-table summary (name, column/measure
counts, categories, format, and a relative path to that table's detail file) plus pointers to
every other output file, so an agent can navigate a large model without loading `metadata.json`.
By default it's written **compact** (no indentation); pass `--pretty` for indented JSON.

Full field-by-field contract — top-level shape, per-table entry, the `tables/<Name>.json` JSON vs.
TOON shapes, and the versioning policy — is documented in
**[docs/index-json-spec.md](https://github.com/Osc2405/pbi-context/blob/main/docs/index-json-spec.md)**.

---

## Use Cases

### 1. Automatic Dashboard Documentation

**Problem:** Your company has multiple undocumented Power BI dashboards. Analysts waste time searching for which measures to use and how tables are related.

**Solution:**
```bash
# Process all dashboards in a folder (English documentation)
pbi-context --batch "data/dashboards/*.pbit"

# Or generate Spanish documentation for all dashboards
pbi-context --batch "data/dashboards/*.pbit" --lang es
```

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
```bash
# English documentation (default)
pbi-context --input "data/pbit/my-model.pbit"

# Spanish documentation
pbi-context --input "data/pbit/my-model.pbit" --lang es
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
```bash
# Compare two versions of the model
pbi-context --diff "data/pbit/dashboard_v1.pbit" "data/pbit/dashboard_v2.pbit"
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

**Impact analysis (`--diff-impact`):** add `--diff-impact` (optionally with `--transitive`) to
also report which measures reference each removed/modified measure **or column** — "what changed,
and what might break" in one call, connecting this diff to the resolver's `find_measure_usages()`
and `find_column_usages()`:

```bash
pbi-context --diff "data/pbit/dashboard_v1.pbit" "data/pbit/dashboard_v2.pbit" --diff-impact --transitive
```

```json
{
  "measures_removed_impact": [
    {"table": "Fact", "name": "Deprecated Measure", "used_by": [{"table": "Fact", "name": "Margin %"}]}
  ],
  "measures_modified_impact": [
    {"table": "Fact", "name": "Total Sales", "used_by": [{"table": "Fact", "name": "YTD Sales"}]}
  ],
  "columns_removed_impact": [
    {"table": "Fact", "name": "Discontinued Flag", "used_by": [{"table": "Fact", "name": "Active Sales"}]}
  ],
  "columns_modified_impact": [
    {"table": "Fact", "name": "Amount", "used_by": [{"table": "Fact", "name": "Total Sales"}]}
  ]
}
```
Removed measures/columns are checked for usages in the *old* model (those references just broke);
modified measures/columns are checked in the *new* model (those callers may now behave
differently). The same capability is exposed to AI agents as the `diff_impact` MCP tool (plus a
standalone `find_column_usages` tool) — see
[MCP server](https://github.com/Osc2405/pbi-context/blob/main/docs/use-cases.md#7-mcp-server---mcp-serve) in docs/use-cases.md.

**Want this enforced automatically before a commit lands?** See
**[docs/pre_commit_hook.md](https://github.com/Osc2405/pbi-context/blob/main/docs/pre_commit_hook.md)** — a reference `git` pre-commit hook
(under [`githooks/`](https://github.com/Osc2405/pbi-context/tree/main/githooks)) for repos that version `.pbip`/`.pbit` models, built on exactly
the command above.

---

More use cases — integrating with AI agents/RAG, chat-invocable Skills for Claude Code and
GitHub Copilot, the `--query` CLI, and the `--mcp-serve` MCP server — are in
**[docs/use-cases.md](https://github.com/Osc2405/pbi-context/blob/main/docs/use-cases.md)**.

---

## Validation

Every efficiency/correctness claim in this README is backed by a dated, reproducible report
against the real `Supply Chain Sample.pbip` fixture (not a synthetic toy model) — read these
before taking "AI-ready" or "token-optimized" at face value:

- **[docs/pbip_validation_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/pbip_validation_report.md)** — end-to-end validation of
  PBIP/TMDL extraction and both output formats against a real (non-synthetic) export; documents
  5 bugs found and fixed in the process.
- **[docs/token_optimization_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/token_optimization_report.md)** — measured token
  cost of raw TMDL vs pbi-context JSON vs TOON across 3 usage scenarios, plus a table-by-table
  breakdown showing TOON is *not* a uniform win (loses on small tables).
- **[docs/precision_validation_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/precision_validation_report.md)** — automated
  proxy for the "does scoped context sacrifice accuracy?" question: 3 isolated agents answer 18
  objectively-gradable questions using only raw TMDL / only JSON / only `--query`. JSON and
  `--query` both scored 18/18; raw TMDL scored 16/18 (the 2 misses were honest `NOT_FOUND` on a
  field TMDL doesn't contain at all, not agent error). Includes an honest caveat about total
  conversation token overhead vs. raw context-source bytes.
- **[docs/scale_validation_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/scale_validation_report.md)** — behavior at 60
  tables/288 measures (synthetic, since no public enterprise-scale PBIP model exists): confirms
  `--index-format auto` and the resolver still hold up, and is transparent about where a fixed
  per-model cost (`index.json`) stops paying for itself at scale.
- **[docs/human_validation_protocol.md](https://github.com/Osc2405/pbi-context/blob/main/docs/human_validation_protocol.md)** *(protocol — not yet
  executed)* — the planned human-subject experiment for validating that scoped context doesn't
  cost real users time or accuracy versus raw file dumps.

---

## DAX Formatting Example

The formatter now generates **hierarchical indentation** that reflects the logical structure of expressions:

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

Common errors, how to verify a fresh install, and installation issues are in
[docs/troubleshooting.md](https://github.com/Osc2405/pbi-context/blob/main/docs/troubleshooting.md).

---

## Comparison with Alternatives

| Feature | pbi-context | Power BI Helper | Dataedo | Manual (DAX Studio) |
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

pbi-context is a read/context-compilation layer, a different category from Microsoft's own Power BI
MCP servers (Modeling MCP for writes, Remote MCP for DAX execution) — complementary rather than
competing.

---

## Generated Documentation Example

Full example of a generated `model_documentation.md`:
[docs/example_output.md](https://github.com/Osc2405/pbi-context/blob/main/docs/example_output.md).

---

## FAQ

### What is pbi-context?
pbi-context is a zero-dependency Python tool that turns a Power BI semantic model
(`.pbit` or the new `.pbip`/TMDL format) into documentation and structured context
that an AI agent can query — Markdown for humans, indexed JSON/JSONL for LLMs and RAG,
a query CLI, and a read-only MCP server.

### How do I give Claude, Copilot, or ChatGPT context about my Power BI model?
Run `pbi-context --input my-model.pbip` to generate the context files, then either upload
`model_documentation.md` to your AI assistant, point an agent at the indexed JSON via
`--query`, or connect an agent directly through the read-only MCP server with `--mcp-serve`.

### Does pbi-context support the new PBIP / TMDL format?
Yes. pbi-context ships a dedicated TMDL parser (not a regex over JSON) that reads `.pbip`
projects, `.SemanticModel/` folders, and `.pbit` templates, auto-detecting the format.

### Does it work with Microsoft Fabric semantic models?
Fabric uses the same TMDL format as PBIP, so compatibility is *expected* — but this has
not yet been validated against a real Fabric export. See [docs/fabric_compatibility.md](https://github.com/Osc2405/pbi-context/blob/main/docs/fabric_compatibility.md).

### How is pbi-context different from Tabular Editor or DAX Studio?
Those are interactive desktop tools for editing and querying models. pbi-context is a
read-only, scriptable context layer: it never modifies your model, has zero .NET/desktop
dependencies, installs with `pip`, and produces LLM-ready output. It's complementary to
Microsoft's own Power BI MCP servers (Modeling MCP for writes, Remote MCP for DAX execution).

### Does pbi-context modify my model?
No. It is strictly read-only — it compiles context and audits changes, never authors or
edits TMDL.

### What does the MCP server do?
It exposes your processed model to an AI agent as queryable tools (list tables, get a
table's measures, search measures, dependency/impact analysis, version diff) over the
standard MCP protocol — so the agent pulls exactly what it needs instead of ingesting the
whole model.

### Does it reduce token usage?
Yes, measurably — with the honest caveat that savings depend on model size and query type,
and can invert at large scale for some scenarios. The headline scenario totals in
[docs/token_optimization_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/token_optimization_report.md) are backed by a real
tokenizer (Gemini's `count_tokens`), not just estimated; some of its finer-grained,
table-by-table breakdowns and the 60-table scale test in
[docs/scale_validation_report.md](https://github.com/Osc2405/pbi-context/blob/main/docs/scale_validation_report.md) still use the standard
chars÷4 approximation, labeled as such everywhere it applies — see [Validation](#validation)
for the full picture, including where the approximation and the real count disagree.

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](https://github.com/Osc2405/pbi-context/blob/main/CONTRIBUTING.md) for the workflow, or use
[GitHub Issues](https://github.com/Osc2405/pbi-context/issues) for bug reports and feature requests.

---

## Help shape pbi-context

Using it on a real model? A 5-minute report of what worked (or didn't) directly guides the
roadmap → [share your experience](https://github.com/Osc2405/pbi-context/issues/new?template=share_your_experience.md).

---

## Roadmap

**Done (v1.1.0, read/context layer):** PBIP/TMDL parsing, indexed output (JSON/TOON), query
resolver + `--query` CLI, read-only MCP server, content-aware `--diff` with impact analysis
(measures and columns), `--export-graph`, a Mermaid ER diagram embedded in the generated docs.
Full history in [CHANGELOG.md](https://github.com/Osc2405/pbi-context/blob/main/CHANGELOG.md).

**Next:** validating with real human users (see [Project Status](#project-status) above) — the
one step between "the numbers look good" and "this actually helps people," and the signal that
would justify expanding scope below.

**Deliberately deferred, pending that signal:**
- **Writing/editing TMDL models** — safely writing TMDL back (preserving formatting, comments,
  lineage tags, merges) is substantially riskier than reading, and Microsoft's own Modeling MCP
  already covers that space.
- **PBIR/report-layer parsing** (pages, visuals, bookmarks) — a different problem from documenting
  the data model, out of scope for now.

*Last updated: 2026-08-03.*

---

## Sample Files

The example files referenced in this documentation are official sample files provided by Microsoft. You can find these and other Power BI sample files in the [Microsoft Power BI Desktop Samples repository](https://github.com/microsoft/powerbi-desktop-samples).

These sample files are excellent for:
- Testing pbi-context functionality
- Learning Power BI data modeling
- Exploring different DAX patterns and measure types
- Understanding relationship structures

To use these samples:
1. Clone or download the repository: `git clone https://github.com/microsoft/powerbi-desktop-samples.git`
2. Open the `.pbix` files in Power BI Desktop
3. Export them as `.pbit` files (File > Export > Power BI Template)
4. Use them with pbi-context to generate documentation

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


