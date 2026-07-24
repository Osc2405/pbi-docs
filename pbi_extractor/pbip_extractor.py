"""
PBIP / TMDL format extractor.
Parses .SemanticModel/ folder structure into a raw_schema dict
compatible with processor.process_schema() — no external dependencies.
"""

from pathlib import Path
from typing import List, Tuple


class PBIPExtractionError(Exception):
    """Base exception for PBIP extraction errors"""
    pass


class SemanticModelNotFoundError(PBIPExtractionError):
    """Cannot locate a .SemanticModel/ folder from the given path"""
    pass


class TmdlParseError(PBIPExtractionError):
    """Error while parsing a .tmdl file"""
    pass


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_name(s: str) -> str:
    """Remove surrounding single quotes from a TMDL identifier."""
    s = s.strip()
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1]
    return s


def _count_tabs(line: str) -> int:
    """Return the number of leading TAB characters."""
    return len(line) - len(line.lstrip("\t"))


def _read_tmdl(path: Path) -> str:
    """Read a .tmdl file, trying UTF-8 then UTF-16."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-16")


# Known scalar properties of a measure block (at depth 2 inside a table).
# DAX expression lines are anything at depth 2 that does NOT match one of these.
_MEASURE_PROPS = frozenset({"formatString", "displayFolder", "description", "annotation",
                             "isHidden", "kpiStatusExpression", "kpiTargetExpression"})


def _classify_measure_line(content: str) -> Tuple[bool, str, str]:
    """
    Decide whether a depth-2 line inside a measure block is a property.
    Returns (is_property, key, value).
    """
    if content == "isHidden":
        return True, "isHidden", ""
    if ": " in content:
        key, _, val = content.partition(": ")
        if key in _MEASURE_PROPS:
            return True, key, val.strip()
    return False, "", ""


def _parse_table_column_ref(ref: str) -> Tuple[str, str]:
    """
    Parse a TMDL column reference into (table_name, column_name).

    Handles both forms:
      Sales.DateKey          →  ("Sales", "DateKey")
      'Date'.'Date'          →  ("Date", "Date")
    """
    ref = ref.strip()
    if ref.startswith("'"):
        close = ref.index("'", 1)
        table = ref[1:close]
        rest = ref[close + 1:].lstrip(".")
        if rest.startswith("'"):
            col = rest[1:rest.index("'", 1)]
        else:
            col = rest
    else:
        dot = ref.find(".")
        if dot >= 0:
            table, col = ref[:dot], _strip_name(ref[dot + 1:])
        else:
            table = col = ref
    return table, col


# ---------------------------------------------------------------------------
# database.tmdl parser
# ---------------------------------------------------------------------------

def _parse_database_tmdl(path: Path) -> int:
    """Return the compatibilityLevel from database.tmdl (default 1604)."""
    for line in _read_tmdl(path).splitlines():
        stripped = line.strip()
        if stripped.startswith("compatibilityLevel:"):
            try:
                return int(stripped.split(":", 1)[1].strip())
            except ValueError:
                pass
    return 1604


# ---------------------------------------------------------------------------
# Table *.tmdl parser
# ---------------------------------------------------------------------------

def _parse_table_tmdl_file(path: Path) -> dict:
    """
    Parse one table .tmdl file.
    Returns a raw table dict matching the structure expected by processor.py.
    """
    table: dict = {
        "name": path.stem,   # fallback; overwritten by 'table <name>' line
        "isHidden": False,
        "columns": [],
        "measures": [],
        "partitions": [],
    }

    block: str = ""          # "column" | "measure" | "partition" | "skip"
    obj: dict = {}
    in_dax: bool = False     # True when accumulating a multi-line DAX expression

    lines = _read_tmdl(path).splitlines()

    for line in lines:
        if not line.rstrip():
            continue

        depth = _count_tabs(line)
        content = line.strip()

        # ── depth 0: table declaration ──────────────────────────────────────
        if depth == 0:
            if content.startswith("table "):
                table["name"] = _strip_name(content[6:].strip())
            continue

        # ── depth 1: start of a new nested block ────────────────────────────
        if depth == 1:
            # Flush the block that just ended
            if block == "column" and obj:
                table["columns"].append(obj)
            elif block == "measure" and obj:
                table["measures"].append(obj)
            elif block == "partition":
                table["partitions"].append({})

            block = ""
            obj = {}
            in_dax = False

            if content == "isHidden":
                table["isHidden"] = True

            elif content.startswith("column "):
                # Calculated columns are declared as `column 'Name' = <DAX expr>`
                # (single-line) or `column 'Name' =` with the DAX body on following
                # lines (multi-line, same pattern as measures); strip the expression
                # either way so it doesn't end up glued onto the name.
                rest = content[7:].strip()
                eq = rest.find(" = ")
                if eq >= 0:
                    c_name = rest[:eq]
                elif rest.endswith(" ="):
                    c_name = rest[:-2]
                else:
                    c_name = rest
                obj = {
                    "name": _strip_name(c_name.strip()),
                    "dataType": "unknown",
                    "isHidden": False,
                    "sourceColumn": "",
                    "formatString": "",
                }
                block = "column"

            elif content.startswith("measure "):
                rest = content[8:].strip()
                eq = rest.find(" = ")
                if eq >= 0:
                    m_name = _strip_name(rest[:eq])
                    m_expr = rest[eq + 3:].strip()
                    if m_expr == "```":
                        # Backtick-fenced multi-line DAX (```<newline>...<newline>```)
                        m_expr = ""
                        in_dax = True
                    else:
                        in_dax = False
                elif rest.endswith(" ="):
                    m_name = _strip_name(rest[:-2])
                    m_expr = ""
                    in_dax = True
                else:
                    m_name = _strip_name(rest)
                    m_expr = ""
                    in_dax = False
                obj = {
                    "name": m_name,
                    "expression": m_expr,
                    "formatString": "",
                    "isHidden": False,
                    "displayFolder": "",
                }
                block = "measure"

            elif content.startswith("partition "):
                block = "partition"

            else:
                block = "skip"

            continue

        # ── depth 2: properties of the current block ─────────────────────────
        if depth == 2:
            if block == "column" and obj:
                if content == "isHidden":
                    obj["isHidden"] = True
                elif ": " in content:
                    key, _, val = content.partition(": ")
                    val = val.strip()
                    if key == "dataType":
                        obj["dataType"] = val
                    elif key == "formatString":
                        obj["formatString"] = val
                    elif key == "sourceColumn":
                        obj["sourceColumn"] = val

            elif block == "measure" and obj:
                if in_dax and content == "```":
                    # closing fence of a ```-delimited multi-line DAX expression
                    in_dax = False
                else:
                    is_prop, key, val = _classify_measure_line(content)
                    if is_prop:
                        in_dax = False
                        if key == "isHidden":
                            obj["isHidden"] = True
                        elif key == "formatString":
                            obj["formatString"] = val
                        elif key == "displayFolder":
                            obj["displayFolder"] = val
                    elif in_dax:
                        # depth-2 line that is not a known property while collecting DAX
                        obj["expression"] = (obj["expression"] + "\n" + content
                                             if obj["expression"] else content)
            continue

        # ── depth ≥ 3: DAX expression continuation ───────────────────────────
        if block == "measure" and obj and in_dax:
            if content == "```":
                # closing fence of a ```-delimited multi-line DAX expression
                in_dax = False
            else:
                obj["expression"] = (obj["expression"] + "\n" + content
                                     if obj["expression"] else content)

    # Flush the last block
    if block == "column" and obj:
        table["columns"].append(obj)
    elif block == "measure" and obj:
        table["measures"].append(obj)
    elif block == "partition":
        table["partitions"].append({})

    return table


# ---------------------------------------------------------------------------
# model.tmdl parser (relationships)
# ---------------------------------------------------------------------------

_CROSS_FILTER_MAP = {
    "bothDirections": "BothDirections",
    "oneDirection":   "OneDirection",
    "automatic":      "Automatic",
}


def _parse_relationships_tmdl(path: Path) -> List[dict]:
    """
    Parse relationship blocks from a .tmdl file.

    Relationships may be embedded in model.tmdl (block at depth 1, properties
    at depth 2) or live in a standalone relationships.tmdl (block at depth 0,
    properties at depth 1). Track the block's own depth so both layouts work.
    """
    relationships: List[dict] = []
    rel: dict = {}
    rel_depth = None

    def _flush():
        if rel:
            relationships.append(rel)

    for line in _read_tmdl(path).splitlines():
        if not line.rstrip():
            continue

        depth = _count_tabs(line)
        content = line.strip()

        if content.startswith("relationship "):
            _flush()
            rel = {
                "name":                 content[13:].strip(),
                "fromTable":            "",
                "fromColumn":           "",
                "toTable":              "",
                "toColumn":             "",
                "fromCardinality":      "many",
                "toCardinality":        "one",
                "crossFilteringBehavior": "OneDirection",
                "isActive":             True,
            }
            rel_depth = depth
            continue

        if rel and rel_depth is not None and depth == rel_depth + 1 and ": " in content:
            key, _, val = content.partition(": ")
            val = val.strip()
            if key == "fromColumn":
                rel["fromTable"], rel["fromColumn"] = _parse_table_column_ref(val)
            elif key == "toColumn":
                rel["toTable"], rel["toColumn"] = _parse_table_column_ref(val)
            elif key == "fromCardinality":
                rel["fromCardinality"] = val
            elif key == "toCardinality":
                rel["toCardinality"] = val
            elif key == "crossFilteringBehavior":
                rel["crossFilteringBehavior"] = _CROSS_FILTER_MAP.get(val, val)
            elif key == "isActive":
                rel["isActive"] = val.lower() not in ("false", "0", "no")

    _flush()
    return relationships


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_semantic_model(input_path: str) -> Path:
    """
    Locate the .SemanticModel/ folder from any supported entry point:
      - A .pbip marker file
      - A project root folder (contains *.SemanticModel/ subfolder)
      - The .SemanticModel/ folder itself
    """
    p = Path(input_path)

    if not p.exists():
        raise SemanticModelNotFoundError(f"Path does not exist: {input_path}")

    # Case 1: the path IS the .SemanticModel folder
    if p.is_dir() and p.name.endswith(".SemanticModel"):
        if (p / "definition" / "model.tmdl").exists():
            return p
        raise SemanticModelNotFoundError(
            f"'{input_path}' looks like a SemanticModel folder but is missing "
            "definition/model.tmdl"
        )

    # Case 2: a .pbip file → look for adjacent .SemanticModel/
    if p.is_file() and p.suffix.lower() == ".pbip":
        sm_dir = p.parent / (p.stem + ".SemanticModel")
        if sm_dir.exists() and sm_dir.is_dir():
            return sm_dir
        raise SemanticModelNotFoundError(
            f"Expected '{sm_dir}' next to '{p.name}' but it was not found"
        )

    # Case 3: project root folder → find *.SemanticModel/ inside
    if p.is_dir():
        candidates = [d for d in p.iterdir()
                      if d.is_dir() and d.name.endswith(".SemanticModel")]
        if candidates:
            return candidates[0]
        raise SemanticModelNotFoundError(
            f"No .SemanticModel/ folder found inside '{input_path}'"
        )

    raise SemanticModelNotFoundError(
        f"Cannot determine PBIP SemanticModel from '{input_path}'. "
        "Supported inputs: .pbip files, .SemanticModel/ folders, or project root folders."
    )


def parse_pbip_model(input_path: str) -> dict:
    """
    Parse a PBIP model from any supported entry point.

    Returns a raw_schema dict with the same structure that
    extractor.parse_datamodel_schema() produces, so processor.process_schema()
    can consume it without changes.

    Raises:
        SemanticModelNotFoundError: if the .SemanticModel/ folder cannot be located
        TmdlParseError: if the relationships file (relationships.tmdl or
            model.tmdl) cannot be parsed. A single corrupt table file under
            tables/ is NOT fatal — it is skipped with a printed warning and
            excluded from the result, matching how .pbit tolerates a bad
            row/table (see processor.py); only the shared relationships file
            aborts the whole model, since it isn't a per-item loop.
        PBIPExtractionError: for any other unexpected error
    """
    sm_dir = find_semantic_model(input_path)
    definition_dir = sm_dir / "definition"

    try:
        db_path = definition_dir / "database.tmdl"
        compat_level = _parse_database_tmdl(db_path) if db_path.exists() else 1604

        tables: List[dict] = []
        tables_dir = definition_dir / "tables"
        if tables_dir.exists():
            for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
                # A single corrupt table file must not abort the whole model —
                # matches processor.py's row-level "skip and warn" philosophy
                # for .pbit (see Pruebas/auditoria_general_2026-07-24.md P1 #3:
                # before this fix, .pbit survived a bad row/table but .pbip
                # aborted entirely on the same class of problem).
                try:
                    tables.append(_parse_table_tmdl_file(tmdl_file))
                except Exception as exc:
                    print(f"Warning: Error parsing table file '{tmdl_file.name}': {exc}")

        # Relationships live either in a standalone relationships.tmdl or
        # embedded in model.tmdl, depending on TMDL version. Prefer the
        # standalone file when present.
        relationships: List[dict] = []
        rel_path = definition_dir / "relationships.tmdl"
        if not rel_path.exists():
            rel_path = definition_dir / "model.tmdl"
        if rel_path.exists():
            try:
                relationships = _parse_relationships_tmdl(rel_path)
            except TmdlParseError:
                raise
            except Exception as exc:
                raise TmdlParseError(
                    f"Error parsing '{rel_path.name}': {exc}"
                ) from exc

        return {
            "compatibilityLevel": compat_level,
            "model": {
                "tables": tables,
                "relationships": relationships,
            },
        }

    except (SemanticModelNotFoundError, TmdlParseError):
        raise
    except Exception as exc:
        raise PBIPExtractionError(
            f"Unexpected error processing '{input_path}': {exc}"
        ) from exc
