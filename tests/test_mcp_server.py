"""
Protocol-level tests for pbi_extractor.mcp_server — spawns the server as a
real subprocess and drives the actual stdio JSON-RPC handshake, no MCP
client library needed (stdlib subprocess + json only).
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pbi_extractor.cli import process_file
from pbi_extractor import resolver
from pbi_extractor import diff as diff_module
from pbi_extractor.indexed_output import write_indexed_output

REPO_ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.pbip"


def _measure(name, expression="1", **overrides):
    m = {"name": name, "expression": expression, "formatted_expression": expression,
         "format_string": "", "is_hidden": False, "display_folder": "", "category": "other"}
    m.update(overrides)
    return m


def _write_synthetic_model_dir(tmp_path, name, tables):
    meta = {"file_name": name, "tables": tables, "relationships": []}
    model_dir = tmp_path / name
    model_dir.mkdir()
    write_indexed_output(meta, model_dir, source_format="pbit")
    with open(model_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return model_dir


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("mcp_server")
    process_file(FIXTURE, out, index_format="json")
    return out / "my-model"


class ServerSession:
    """Drives one MCP stdio handshake against a live subprocess."""

    def __init__(self, model_dir):
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "pbi_extractor.mcp_server", str(model_dir)],
            cwd=REPO_ROOT,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
        )
        self._next_id = 1

    def request(self, method, params=None):
        msg_id = self._next_id
        self._next_id += 1
        self.proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": msg_id, "method": method, "params": params or {},
        }) + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        assert line, f"No response from server (stderr: {self.proc.stderr.read()})"
        return json.loads(line)

    def notify(self, method, params=None):
        self.proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "method": method, "params": params or {},
        }) + "\n")
        self.proc.stdin.flush()

    def call_tool(self, name, arguments=None):
        return self.request("tools/call", {"name": name, "arguments": arguments or {}})

    def close(self):
        self.proc.stdin.close()
        self.proc.wait(timeout=5)


@pytest.fixture
def session(model_dir):
    s = ServerSession(model_dir)
    s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}})
    s.notify("notifications/initialized")
    yield s
    s.close()


def test_initialize_response_shape(model_dir):
    s = ServerSession(model_dir)
    resp = s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    assert resp["result"]["protocolVersion"] == "2025-06-18"
    assert resp["result"]["serverInfo"]["name"] == "pbi-docs"
    assert "tools" in resp["result"]["capabilities"]
    s.close()


def test_tools_list_has_nine_tools(session):
    resp = session.request("tools/list")
    tools = resp["result"]["tools"]
    names = {t["name"] for t in tools}
    assert names == {"list_tables", "get_table", "get_measure",
                      "search_measures", "search_columns", "get_relationships",
                      "get_measure_dependencies", "find_measure_usages", "diff_impact"}
    for t in tools:
        assert "description" in t
        assert t["inputSchema"]["type"] == "object"


def test_tools_call_list_tables_matches_resolver(session, model_dir):
    resp = session.call_tool("list_tables")
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.list_tables(model_dir)


def test_tools_call_get_table_matches_resolver(session, model_dir):
    resp = session.call_tool("get_table", {"table_name": "Sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.get_table(model_dir, "Sales")


def test_tools_call_get_measure_matches_resolver(session, model_dir):
    resp = session.call_tool("get_measure", {"table_name": "Sales", "measure_name": "Total Sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.get_measure(model_dir, "Sales", "Total Sales")


def test_tools_call_search_measures_matches_resolver(session, model_dir):
    resp = session.call_tool("search_measures", {"query": "sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.search_measures(model_dir, "sales")


def test_tools_call_search_columns_matches_resolver(session, model_dir):
    resp = session.call_tool("search_columns", {"query": "sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.search_columns(model_dir, "sales")


def test_tools_call_get_relationships_matches_resolver(session, model_dir):
    resp = session.call_tool("get_relationships", {"table": "Date"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.get_relationships(model_dir, table="Date")


def test_tools_call_get_measure_dependencies_matches_resolver(session, model_dir):
    resp = session.call_tool("get_measure_dependencies", {"table_name": "Sales", "measure_name": "YTD Sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.get_measure_dependencies(model_dir, "Sales", "YTD Sales")


def test_tools_call_find_measure_usages_matches_resolver(session, model_dir):
    resp = session.call_tool("find_measure_usages", {"table_name": "Sales", "measure_name": "Total Sales"})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.find_measure_usages(model_dir, "Sales", "Total Sales")


def test_tools_call_get_measure_dependencies_transitive(session, model_dir):
    resp = session.call_tool("get_measure_dependencies",
                              {"table_name": "Sales", "measure_name": "YTD Sales", "transitive": True})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.get_measure_dependencies(model_dir, "Sales", "YTD Sales", transitive=True)
    assert payload["transitive"] is True


def test_tools_call_find_measure_usages_transitive(session, model_dir):
    resp = session.call_tool("find_measure_usages",
                              {"table_name": "Sales", "measure_name": "Total Sales", "transitive": True})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload == resolver.find_measure_usages(model_dir, "Sales", "Total Sales", transitive=True)


def test_tools_call_unknown_table_is_error_not_crash(session):
    resp = session.call_tool("get_table", {"table_name": "DoesNotExist"})
    assert resp["result"]["isError"] is True
    assert "Unknown table" in resp["result"]["content"][0]["text"]


def test_tools_call_unknown_tool_returns_jsonrpc_error(session):
    resp = session.call_tool("not_a_real_tool")
    assert "error" in resp
    assert resp["error"]["code"] == -32601


def test_ping(session):
    resp = session.request("ping")
    assert resp["result"] == {}


def test_importing_mcp_server_does_not_break_cli_logging(model_dir):
    """
    Regression test: mcp_server.py must not call logging.basicConfig() at
    module import time. cli.py does `from . import mcp_server`, and
    logging.basicConfig() is a no-op after the first call in a process — an
    import-time call there previously hijacked cli.py's own setup_logging(),
    silently breaking --verbose and mislabeling every log line as
    "mcp_server" instead of "__main__" for the whole CLI, not just
    --mcp-serve.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pbi_extractor.cli", "-i", str(FIXTURE),
         "-o", str(model_dir.parent / "verbose_check"), "--verbose"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert " - __main__ - DEBUG - " in result.stderr
    assert " - mcp_server - " not in result.stderr


# ---------------------------------------------------------------------------
# diff_impact tool
# ---------------------------------------------------------------------------

def test_tools_call_diff_impact_against_itself_is_empty(session, model_dir):
    resp = session.call_tool("diff_impact", {"other_model_dir": str(model_dir)})
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["measures_added"] == []
    assert payload["measures_removed"] == []
    assert payload["measures_modified"] == []
    assert payload["measures_removed_impact"] == []
    assert payload["measures_modified_impact"] == []


def test_tools_call_diff_impact_matches_direct_call(session, model_dir):
    resp = session.call_tool("diff_impact", {"other_model_dir": str(model_dir), "transitive": True})
    payload = json.loads(resp["result"]["content"][0]["text"])
    expected = diff_module.diff_with_impact(model_dir, model_dir, transitive=True)
    assert payload == expected


def test_tools_call_diff_impact_reports_real_impact(tmp_path):
    older = _write_synthetic_model_dir(tmp_path, "older", [
        {"name": "Sales", "columns": [], "measures": [
            _measure("Total Sales"),
            _measure("Margin", expression="[Total Sales] * 0.1"),
        ]},
    ])
    newer = _write_synthetic_model_dir(tmp_path, "newer", [
        {"name": "Sales", "columns": [], "measures": [
            _measure("Margin", expression="[Total Sales] * 0.1"),
        ]},
    ])

    s = ServerSession(newer)
    s.request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                              "clientInfo": {"name": "test", "version": "0"}})
    s.notify("notifications/initialized")
    resp = s.call_tool("diff_impact", {"other_model_dir": str(older)})
    s.close()

    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["measures_removed"] == [["Sales", "Total Sales"]]
    assert payload["measures_removed_impact"] == [
        {"table": "Sales", "name": "Total Sales",
         "used_by": [{"table": "Sales", "name": "Margin"}]}
    ]


def test_tools_call_diff_impact_missing_other_model_dir_is_error(session):
    resp = session.call_tool("diff_impact", {"other_model_dir": "/does/not/exist"})
    assert resp["result"]["isError"] is True
