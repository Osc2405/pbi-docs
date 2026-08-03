# Additional Use Cases: AI Agent & Automation Integrations

See the main [README](../README.md#use-cases) for the first three use cases (dashboard
documentation, analyst onboarding, model auditing). These four cover integrating pbi-context output
into AI agents, chat assistants, and automation.

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

**Solution:** pbi-context ships two chat-invocable skills that run the extractor and then query the
model on demand via `pbi-context --query` (see below) instead of dumping whole files into context:

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
pbi-context --query output/my-model --list-tables                                 # table summaries
pbi-context --query output/my-model --list-tables --category revenue              # filtered
pbi-context --query output/my-model --table "Sales"                               # one table, full detail
pbi-context --query output/my-model --table "Sales" --measure "Total Sales"       # one measure, full record
pbi-context --query output/my-model --search-measures "revenue"                   # cross-table measure search
pbi-context --query output/my-model --search-columns "customer"                   # cross-table column search
pbi-context --query output/my-model --relationships --table "Sales"               # relationships touching a table
pbi-context --query output/my-model --table "Sales" --column "SalesAmount" --usages  # column impact analysis
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
exposing 10 tools — thin wrappers around `resolver.py`/`diff.py`: `list_tables`, `get_table`,
`get_measure`, `search_measures`, `search_columns`, `get_relationships`,
`get_measure_dependencies`, `find_measure_usages`, `find_column_usages`, and `diff_impact`
(compare against another already-processed model directory and report which measures depend on
each removed/modified measure or column — "what changed and what might break" for an agent
auditing an edit).

```bash
pbi-context --mcp-serve output/my-model
```

Configure it in your client's MCP settings (e.g. `claude_desktop_config.json` or Claude Code's
`.mcp.json`):

```json
{
  "mcpServers": {
    "pbi-context": {
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

**This repo ships its own `.mcp.json`** (project root) pointing at the `Sales Sample`
validation fixture — a dev/demo convenience for testing `mcp_server.py` itself against a real
MCP client, not a template end users need (real usage is the config above, pointed at your own
processed model). To verify it against Claude Code:

1. Process the fixture first: `pbi-context -i "files_test/Sales Sample.pbip" -o output`.
2. Restart/reload Claude Code in this project (or open a fresh session here) — project-scoped
   `.mcp.json` servers require a session (re)start to be picked up.
3. Run `/mcp` — `pbi-context` shows as `⏸ Pending approval` the first time; approve it.
4. Run `/mcp` again — should show connected, 10 tools.
5. Ask something like *"what tables does this Power BI model have"* — Claude should call
   `mcp__pbi-context__list_tables` directly (visible in the transcript), not read any file.

This last step is the one thing about the MCP server that automated tests
(`tests/test_mcp_server.py`) can't cover — they prove protocol correctness against a harness I
wrote myself, not that a real client actually discovers and calls the tools.

### 8. Exporting the relationship graph (`--export-graph`)

**Problem:** You want to visualize how a model's tables connect — in Gephi, yEd, or a Python/JS
graph library — instead of reading `relationships.json` by hand.

**Solution:** `--export-graph` (a `--query` mode flag, like `--dependencies`/`--usages`) projects
`list_tables()`/`get_relationships()` to a generic `{"nodes": [...], "edges": [...]}` graph — every
table is a node (including isolated ones with no relationships, unlike the Mermaid diagram in
`model_documentation.md`, which omits them for readability), every relationship is a directed edge
(`from_table -> to_table`, same direction used throughout the codebase).

```bash
pbi-context --query output/my-model --export-graph               # JSON node/edge lists (default)
pbi-context --query output/my-model --export-graph graphml > model.graphml   # GraphML XML
```

GraphML has no scalar attribute type for lists, so a table's `categories` (an array in the JSON
output) is flattened to a comma-joined string in GraphML only — a documented format difference,
not a bug. Not exposed as an MCP tool: an agent that already has `list_tables`/`get_relationships`
as tools can reconstruct the same information without a GraphML/XML blob in its context (see
`CLAUDE.md` section 4).
