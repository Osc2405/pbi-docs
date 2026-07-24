"""
Query resolver — structured, on-demand access to an already-generated
output directory (index.json + tables/*.json + relationships.json).

Normalizes JSON vs TOON transparently: callers never see the
{__toon, __fields, __rows} wrapper, regardless of which --index-format
produced the files. This is the precursor to an MCP server: each MCP
tool would be a thin wrapper around one of these functions.
"""

import json
import re
from pathlib import Path
from typing import List, Optional

from .indexed_output import safe_filename, flatten_measure
from .toon_encoder import decode_toon


class ResolverError(Exception):
    """Base exception for resolver errors."""
    pass


# path (resolved, as str) -> (mtime, parsed dict). mcp_server.py binds one
# long-lived process to one model_dir and calls resolver functions repeatedly
# (list/search operations call get_table() once per table each time) — every
# call used to re-read and re-parse the same files from disk with no reuse
# across calls (docs/scale_validation_report.md section 5 fixed the same
# problem only *within* a single transitive call, not across separate tool
# calls). Keyed by mtime rather than cached forever so reprocessing a model
# while a server is bound to it is picked up instead of serving stale data.
_JSON_CACHE: dict = {}


def _load_json(path: Path) -> dict:
    if not path.exists():
        raise ResolverError(f"Not found: {path}. Run pbi-docs on the model first.")
    key = str(path.resolve())
    mtime = path.stat().st_mtime
    cached = _JSON_CACHE.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _JSON_CACHE[key] = (mtime, data)
    return data


def _maybe_decode(value):
    """Decode a TOON block if present, otherwise return the value unchanged."""
    if isinstance(value, dict) and value.get("__toon"):
        return decode_toon(value)
    return value


def load_index(model_dir: Path) -> dict:
    """Load index.json for an already-processed model output directory."""
    return _load_json(Path(model_dir) / "index.json")


def load_metadata(model_dir: Path) -> dict:
    """Load metadata.json (the full cleaned_metadata dict) for an
    already-processed model output directory. Used by diff.py's
    model_dir-based wrappers, which need the in-memory dict shape
    diff_models() operates on, not the indexed output."""
    return _load_json(Path(model_dir) / "metadata.json")


def list_tables(model_dir: Path, *, hidden: Optional[bool] = None,
                 technical: Optional[bool] = None,
                 category: Optional[str] = None) -> List[dict]:
    """Return index.json's table summaries, optionally filtered."""
    tables = load_index(model_dir)["tables"]
    if hidden is not None:
        tables = [t for t in tables if t["is_hidden"] == hidden]
    if technical is not None:
        tables = [t for t in tables if t["is_technical"] == technical]
    if category is not None:
        tables = [t for t in tables if category in t.get("categories", [])]
    return tables


def get_table(model_dir: Path, table_name: str, *, include_dax: bool = True) -> dict:
    """
    Return one table's full detail: name, flags, columns, and a unified
    `measures` list (merging measures_flat + measures_dax by name when the
    source is TOON; plain-JSON sources already have this shape).

    Raises ResolverError with the list of available names if table_name
    doesn't exist.
    """
    model_dir = Path(model_dir)

    # The table's filename is fully determined by its name (safe_filename is
    # a pure function), so a point lookup never needs index.json on the happy
    # path — only load it as a fallback to build the "available tables" error
    # message once we already know the direct read failed. At model scale,
    # index.json's fixed cost dwarfs a single table file (docs/scale_validation_report.md
    # section 4: it was ~10x the size of the table being looked up on a
    # 60-table model), so skipping it here is the fix for that finding.
    fname = safe_filename(table_name) + ".json"
    table_path = model_dir / "tables" / fname
    detail = None
    if table_path.exists():
        candidate = _load_json(table_path)
        # safe_filename() isn't guaranteed collision-free (two differently
        # named tables could sanitize to the same filename), so confirm the
        # file we found is actually this table before trusting it.
        if candidate.get("name") == table_name:
            detail = candidate

    if detail is None:
        names = [t["name"] for t in load_index(model_dir)["tables"]]
        raise ResolverError(f"Unknown table '{table_name}'. Available tables: {names}")

    columns = _maybe_decode(detail.get("columns", []))

    # Normalize to one canonical shape regardless of source format: JSON
    # measures carry raw `expression` and no `complexity`; TOON measures
    # (measures_flat + measures_dax) carry `complexity` and no raw
    # `expression`. Build the same 7 keys either way, using
    # indexed_output.flatten_measure() as the single source of truth for the
    # first 6 (see CHANGELOG: this used to be duplicated field-by-field here).
    if "measures_flat" in detail:
        # Already written via flatten_measure()+MEASURE_FLAT_FIELDS at
        # indexed_output.py write time, so the decoded rows already carry
        # exactly the 6 canonical keys — just attach the DAX body.
        flat = _maybe_decode(detail["measures_flat"])
        dax_by_name = {m["name"]: m.get("formatted_expression", "")
                       for m in detail.get("measures_dax", [])}
        measures = [
            {**m, "formatted_expression": dax_by_name.get(m["name"], "")}
            for m in flat
        ]
    else:
        measures = [
            {**flatten_measure(m), "formatted_expression": m.get("formatted_expression", "")}
            for m in detail.get("measures", [])
        ]

    if not include_dax:
        measures = [{k: v for k, v in m.items() if k != "formatted_expression"}
                    for m in measures]

    return {
        "name": detail["name"],
        "is_hidden": detail.get("is_hidden", False),
        "is_technical": detail.get("is_technical", False),
        "partition_count": detail.get("partition_count", 0),
        "columns": columns,
        "measures": measures,
    }


def get_relationships(model_dir: Path, *, table: Optional[str] = None) -> List[dict]:
    """Return relationships.json, optionally filtered to those touching `table`."""
    rels = _maybe_decode(_load_json(Path(model_dir) / "relationships.json"))
    if table is not None:
        rels = [r for r in rels if table in (r["from_table"], r["to_table"])]
    return rels


def search_measures(model_dir: Path, query: str, *, category: Optional[str] = None) -> List[dict]:
    """
    Case-insensitive substring search for a measure name across every table.
    Returns one entry per match: table + the measure's fields (no DAX body,
    use get_table() for that once you know which table/measure you need).
    """
    query_lower = query.lower()
    results = []
    for t in list_tables(model_dir):
        table = get_table(model_dir, t["name"], include_dax=False)
        for m in table["measures"]:
            if query_lower not in m["name"].lower():
                continue
            if category is not None and m.get("category") != category:
                continue
            results.append({"table": table["name"], **m})
    return results


def get_measure(model_dir: Path, table_name: str, measure_name: str) -> dict:
    """
    Return one measure's full record (including DAX) from a known table.
    Cheaper/more precise than get_table() when the table and measure name
    are already known. Raises ResolverError if either isn't found.
    """
    table = get_table(model_dir, table_name)
    for m in table["measures"]:
        if m["name"] == measure_name:
            return {"table": table_name, **m}
    names = [m["name"] for m in table["measures"]]
    raise ResolverError(f"Unknown measure '{measure_name}' in table '{table_name}'. "
                         f"Available measures: {names}")


def search_columns(model_dir: Path, query: str, *, category: Optional[str] = None) -> List[dict]:
    """
    Case-insensitive substring search for a column name across every table.
    Mirrors search_measures() — answers "which table has a column called X".
    """
    query_lower = query.lower()
    results = []
    for t in list_tables(model_dir):
        table = get_table(model_dir, t["name"], include_dax=False)
        for c in table["columns"]:
            if query_lower not in c["name"].lower():
                continue
            if category is not None and c.get("category") != category:
                continue
            results.append({"table": table["name"], **c})
    return results


# ---------------------------------------------------------------------------
# Dependency / impact-analysis queries (Horizonte 3: "compound questions")
# ---------------------------------------------------------------------------
#
# Regex-based, not a DAX parser: enough to answer "what does this measure
# reference" / "what references this measure", not a substitute for actually
# evaluating DAX. Matched in priority order at each scan position:
#   'Table'[Column]  -> quoted table + column
#   Table[Column]    -> bareword table + column (DAX only requires quoting an
#                       identifier when it contains spaces/special chars, so a
#                       bareword table name is always a simple identifier)
#   [Something]      -> ambiguous: DAX allows a bare `[X]` to mean either a
#                       measure reference OR an unqualified reference to a
#                       column of the *same* table the expression's own
#                       measure lives on (e.g. `SUM([Value])` inside a Fact
#                       measure, meaning Fact[Value]). Disambiguated against
#                       the owning table's real column names — only treated
#                       as a measure if no such column exists. See CHANGELOG
#                       for the real-world model that exposed this.

_REFERENCE_RE = re.compile(
    r"'(?P<qtable>[^']+)'\[(?P<qcol>[^\]]+)\]"
    r"|(?P<btable>[A-Za-z_]\w*)\[(?P<bcol>[^\]]+)\]"
    r"|\[(?P<measure>[^\]]+)\]"
)


def _extract_references(expression: str, own_table: Optional[str] = None,
                         own_columns: Optional[set] = None) -> dict:
    """Parse [Measure] and Table[Column] references out of a DAX expression.

    `own_table`/`own_columns` disambiguate a bare `[X]` match: if X names a
    column on the table the expression itself belongs to, it's classified as
    that column, not a measure reference.
    """
    own_columns = own_columns or set()
    columns = []
    measures = []
    for m in _REFERENCE_RE.finditer(expression or ""):
        if m.group("qtable") is not None:
            columns.append({"table": m.group("qtable"), "column": m.group("qcol")})
        elif m.group("btable") is not None:
            columns.append({"table": m.group("btable"), "column": m.group("bcol")})
        else:
            name = m.group("measure")
            if name in own_columns:
                columns.append({"table": own_table, "column": name})
            else:
                measures.append(name)
    return {"columns": columns, "measures": measures}


def _all_measures(model_dir: Path) -> List[dict]:
    """Every measure in the model as {table, name, expression, own_columns}.
    own_columns (the table's own column names) is threaded through to
    _extract_references() to disambiguate bare [X] references."""
    out = []
    for t in list_tables(model_dir):
        table = get_table(model_dir, t["name"])
        own_columns = {c["name"] for c in table["columns"]}
        for m in table["measures"]:
            out.append({"table": table["name"], "name": m["name"],
                        "expression": m.get("formatted_expression", ""),
                        "own_columns": own_columns})
    return out


def _measure_table_map(model_dir: Path) -> dict:
    """name -> table for every measure in the model (DAX measure names are
    unique model-wide, so this is unambiguous)."""
    return {m["name"]: m["table"] for m in _all_measures(model_dir)}


def get_measure_dependencies(model_dir: Path, table_name: str, measure_name: str,
                              *, transitive: bool = False) -> dict:
    """
    What a measure references: other measures (by name) and columns (by
    table + column), parsed from its DAX expression.

    One level deep by default — call again on a referenced measure to go
    further. Pass transitive=True to follow the chain automatically (BFS,
    cycle-safe) and get the full closure of measures/columns touched,
    directly or indirectly.
    """
    if not transitive:
        table = get_table(model_dir, table_name)
        measure = next((m for m in table["measures"] if m["name"] == measure_name), None)
        if measure is None:
            names = [m["name"] for m in table["measures"]]
            raise ResolverError(f"Unknown measure '{measure_name}' in table '{table_name}'. "
                                 f"Available measures: {names}")
        own_columns = {c["name"] for c in table["columns"]}
        refs = _extract_references(measure.get("formatted_expression", ""), table_name, own_columns)

        referenced_measures = sorted({name for name in refs["measures"] if name != measure_name})

        seen = set()
        referenced_columns = []
        for c in refs["columns"]:
            key = (c["table"], c["column"])
            if key not in seen:
                seen.add(key)
                referenced_columns.append(c)

        return {
            "table": table_name,
            "measure": measure_name,
            "references_measures": referenced_measures,
            "references_columns": referenced_columns,
        }

    table_by_name = _measure_table_map(model_dir)
    visited = {(table_name, measure_name)}
    queue = [(table_name, measure_name)]
    all_measures = set()
    seen_columns = set()
    all_columns = []

    while queue:
        t, m = queue.pop(0)
        direct = get_measure_dependencies(model_dir, t, m, transitive=False)
        for name in direct["references_measures"]:
            all_measures.add(name)
            next_table = table_by_name.get(name)
            if next_table is None:
                continue  # can't resolve to a table (e.g. unknown/typo'd reference) — leaf node
            key = (next_table, name)
            if key not in visited:
                visited.add(key)
                queue.append(key)
        for c in direct["references_columns"]:
            ckey = (c["table"], c["column"])
            if ckey not in seen_columns:
                seen_columns.add(ckey)
                all_columns.append(c)

    all_measures.discard(measure_name)  # a cycle back to the start shouldn't count as self-dependency

    return {
        "table": table_name,
        "measure": measure_name,
        "references_measures": sorted(all_measures),
        "references_columns": all_columns,
        "transitive": True,
    }


def find_measure_usages(model_dir: Path, table_name: str, measure_name: str,
                         *, transitive: bool = False) -> List[dict]:
    """
    Impact analysis: which other measures reference this one in their DAX
    expression.

    One level deep (direct references only) by default. Pass
    transitive=True to follow the chain automatically (BFS, cycle-safe) and
    get everything downstream, directly or indirectly affected.
    Raises ResolverError if table_name/measure_name doesn't exist.
    """
    get_measure(model_dir, table_name, measure_name)  # validates existence

    # Fetched once and reused for every hop below — every hop needs to scan
    # the same full measure list (an "is this used" query has no way around
    # scanning everything), so re-reading it from disk per hop is pure waste.
    # On a 60-table/288-measure synthetic model this took a transitive lookup
    # from 0.002s to 1.6s (docs/scale_validation_report.md section 5).
    all_measures = _all_measures(model_dir)

    def _usages_of(t: str, m: str) -> List[dict]:
        usages = []
        for entry in all_measures:
            if entry["table"] == t and entry["name"] == m:
                continue
            refs = _extract_references(entry["expression"], entry["table"], entry["own_columns"])
            if m in refs["measures"]:
                usages.append({"table": entry["table"], "name": entry["name"]})
        return usages

    if not transitive:
        return _usages_of(table_name, measure_name)

    visited = {(table_name, measure_name)}
    queue = [(table_name, measure_name)]
    all_usages = {}  # (table, name) -> record, dict preserves discovery order

    while queue:
        t, m = queue.pop(0)
        for u in _usages_of(t, m):
            key = (u["table"], u["name"])
            all_usages.setdefault(key, u)
            if key not in visited:
                visited.add(key)
                queue.append(key)

    return list(all_usages.values())
