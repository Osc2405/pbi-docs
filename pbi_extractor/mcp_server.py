"""
Read-only MCP server, hand-rolled against the stable spec (2025-06-18):
newline-delimited JSON-RPC 2.0 over stdio. No external dependencies —
the official `mcp` SDK pulls in pydantic/anyio/httpx/starlette/uvicorn,
which would contradict this project's zero-dependency stance.

One server instance is bound to one already-processed model output
directory (passed as a CLI arg at launch), mirroring how the filesystem
MCP server is rooted to a directory. Each tool is a thin wrapper around
a resolver.py function.

stdout is the JSON-RPC channel — nothing but protocol messages may be
written there. Logging goes to stderr.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

from . import resolver
from .resolver import ResolverError
from . import diff
from . import __version__

PROTOCOL_VERSION = "2025-06-18"

logger = logging.getLogger(__name__)


TOOLS = [
    {
        "name": "list_tables",
        "description": "List tables in the model with hidden/technical flags, column/measure "
                        "counts, partition counts, and measure categories present. Optionally filter.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "hidden": {"type": "boolean", "description": "Only hidden (true) or visible (false) tables"},
                "technical": {"type": "boolean", "description": "Only technical (true) or business (false) tables"},
                "category": {"type": "string", "description": "Only tables with a measure in this category"},
            },
        },
    },
    {
        "name": "get_table",
        "description": "Get one table's full detail: columns and measures (with DAX). "
                        "Use list_tables first if you don't know the exact table name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "include_dax": {"type": "boolean", "description": "Include formatted DAX (default true)"},
            },
            "required": ["table_name"],
        },
    },
    {
        "name": "get_measure",
        "description": "Get one measure's full record (including DAX) from a known table. "
                        "Cheaper than get_table when you already know the table and measure name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "measure_name": {"type": "string"},
            },
            "required": ["table_name", "measure_name"],
        },
    },
    {
        "name": "search_measures",
        "description": "Find measures by a case-insensitive name substring across every table "
                        "— use for 'which tables have a revenue measure' style questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_columns",
        "description": "Find columns by a case-insensitive name substring across every table "
                        "— use for 'which table has a column called X' style questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "category": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_relationships",
        "description": "List relationships, optionally filtered to those touching one table.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table": {"type": "string"},
            },
        },
    },
    {
        "name": "get_measure_dependencies",
        "description": "What a measure references: other measures and columns, parsed from its "
                        "DAX expression. One level deep by default. Use for 'what does this "
                        "measure depend on' style questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "measure_name": {"type": "string"},
                "transitive": {"type": "boolean",
                               "description": "Follow the chain and return the full closure "
                                              "(default false: one level deep only)"},
            },
            "required": ["table_name", "measure_name"],
        },
    },
    {
        "name": "find_measure_usages",
        "description": "Impact analysis: which other measures reference this one in their DAX "
                        "expression. One level deep by default. Use for 'what breaks if I change "
                        "this measure' style questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "measure_name": {"type": "string"},
                "transitive": {"type": "boolean",
                               "description": "Follow the chain and return everything downstream "
                                              "(default false: direct references only)"},
            },
            "required": ["table_name", "measure_name"],
        },
    },
    {
        "name": "find_column_usages",
        "description": "Impact analysis: which measures reference this column in their DAX "
                        "expression. One level deep by default. Use for 'what breaks if I remove "
                        "this column' style questions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "table_name": {"type": "string"},
                "column_name": {"type": "string"},
                "transitive": {"type": "boolean",
                               "description": "Follow the chain and return everything downstream "
                                              "(default false: direct references only)"},
            },
            "required": ["table_name", "column_name"],
        },
    },
    {
        "name": "diff_impact",
        "description": "Compare the bound model against another already-processed model "
                        "directory: added/removed/modified measures, columns, relationships, "
                        "plus impact analysis (which measures reference each removed/modified "
                        "measure or column). Use for 'what changed and what might break' after "
                        "editing a model. Both directories must already be processed by pbi-docs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "other_model_dir": {"type": "string",
                                    "description": "Path to the other processed model's output directory"},
                "other_is_before": {"type": "boolean",
                                    "description": "true (default): other_model_dir is the OLDER "
                                                   "version, the bound model is the NEWER one. "
                                                   "Set false to reverse that."},
                "transitive": {"type": "boolean",
                               "description": "Follow the impact chain beyond one level (default false)"},
            },
            "required": ["other_model_dir"],
        },
    },
]

_DISPATCH = {
    "list_tables": lambda model_dir, a: resolver.list_tables(
        model_dir, hidden=a.get("hidden"), technical=a.get("technical"), category=a.get("category")),
    "get_table": lambda model_dir, a: resolver.get_table(
        model_dir, a["table_name"], include_dax=a.get("include_dax", True)),
    "get_measure": lambda model_dir, a: resolver.get_measure(
        model_dir, a["table_name"], a["measure_name"]),
    "search_measures": lambda model_dir, a: resolver.search_measures(
        model_dir, a["query"], category=a.get("category")),
    "search_columns": lambda model_dir, a: resolver.search_columns(
        model_dir, a["query"], category=a.get("category")),
    "get_relationships": lambda model_dir, a: resolver.get_relationships(
        model_dir, table=a.get("table")),
    "get_measure_dependencies": lambda model_dir, a: resolver.get_measure_dependencies(
        model_dir, a["table_name"], a["measure_name"], transitive=a.get("transitive", False)),
    "find_measure_usages": lambda model_dir, a: resolver.find_measure_usages(
        model_dir, a["table_name"], a["measure_name"], transitive=a.get("transitive", False)),
    "find_column_usages": lambda model_dir, a: resolver.find_column_usages(
        model_dir, a["table_name"], a["column_name"], transitive=a.get("transitive", False)),
    "diff_impact": lambda model_dir, a: (
        diff.diff_with_impact(a["other_model_dir"], model_dir, transitive=a.get("transitive", False))
        if a.get("other_is_before", True)
        else diff.diff_with_impact(model_dir, a["other_model_dir"], transitive=a.get("transitive", False))
    ),
}


def _write(msg: dict) -> None:
    print(json.dumps(msg), flush=True)


def _handle(model_dir: Path, msg: dict) -> Optional[dict]:
    """Return a response dict, or None for notifications (no reply expected)."""
    method = msg.get("method")
    msg_id = msg.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": msg_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pbi-docs", "version": __version__},
            },
        }

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        params = msg.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        handler = _DISPATCH.get(tool_name)
        if handler is None:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}}
        try:
            result = handler(model_dir, arguments)
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(result)}]}}
        except ResolverError as e:
            return {"jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text", "text": str(e)}], "isError": True}}

    if msg_id is not None:
        return {"jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}}
    return None


def run(model_dir: Path) -> None:
    """Block reading JSON-RPC messages from stdin until EOF."""
    # No-op if logging is already configured (e.g. by cli.py when dispatched via
    # --mcp-serve) — only takes effect when this module runs standalone
    # (`python -m pbi_extractor.mcp_server`), where nothing has configured
    # logging yet. Must go to stderr: stdout is the JSON-RPC channel.
    logging.basicConfig(stream=sys.stderr, level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    model_dir = Path(model_dir)
    logger.info(f"pbi-docs MCP server starting, bound to: {model_dir}")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError as e:
            logger.error(f"Malformed JSON-RPC line: {e}")
            continue
        response = _handle(model_dir, msg)
        if response is not None:
            _write(response)
    logger.info("stdin closed, shutting down")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m pbi_extractor.mcp_server <model-output-dir>", file=sys.stderr)
        sys.exit(1)
    run(Path(sys.argv[1]))
