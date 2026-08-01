"""
Utilities for comparing two models (cleaned_metadata) and producing a
content-aware diff: not just which measures/columns/relationships were
added or removed, but which existing ones changed content.
"""

import re
from typing import Dict, List, Tuple

from . import resolver

_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_dax(expr: str) -> str:
    """Strip all whitespace, for the semantic-vs-cosmetic DAX comparison
    below — DAX has no whitespace-sensitive syntax, so a pure reindent/
    reflow (e.g. `SUM(Sales[Amount])` vs `SUM(\\n\\tSales[Amount]\\n)`)
    should compare equal."""
    return _WHITESPACE_RE.sub("", expr or "")


def _index_by(items: List[dict], key_fields: Tuple[str, ...]) -> Dict[tuple, dict]:
    return {tuple(item.get(f, "") for f in key_fields): item for item in items}


def _diff_field_changes(a: dict, b: dict, fields: List[str]) -> dict:
    """Return {field: {"old": ..., "new": ...}} for every field that differs."""
    changes = {}
    for field in fields:
        old, new = a.get(field, ""), b.get(field, "")
        if old != new:
            changes[field] = {"old": old, "new": new}
    return changes


def _all_measures(meta: dict) -> Dict[Tuple[str, str], dict]:
    items = []
    for t in meta.get("tables", []):
        for m in t.get("measures", []):
            items.append({"table": t.get("name", "?"), **m})
    return _index_by(items, ("table", "name"))


def _all_columns(meta: dict) -> Dict[Tuple[str, str], dict]:
    items = []
    for t in meta.get("tables", []):
        for c in t.get("columns", []):
            items.append({"table": t.get("name", "?"), **c})
    return _index_by(items, ("table", "name"))


def _all_relationships(meta: dict) -> Dict[Tuple[str, str, str, str], dict]:
    return _index_by(meta.get("relationships", []),
                      ("from_table", "from_column", "to_table", "to_column"))


_MEASURE_CONTENT_FIELDS = ["format_string", "display_folder", "is_hidden", "category"]
_COLUMN_FIELDS = ["data_type", "format_string", "category", "is_hidden", "source_column"]
_RELATIONSHIP_FIELDS = ["cardinality", "cross_filtering", "is_active"]


def _diff_measures(a_measures: dict, b_measures: dict) -> Tuple[list, list, list]:
    a_keys, b_keys = set(a_measures), set(b_measures)
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)

    modified = []
    for key in sorted(a_keys & b_keys):
        a_m, b_m = a_measures[key], b_measures[key]
        changes = _diff_field_changes(a_m, b_m, _MEASURE_CONTENT_FIELDS)

        a_norm = _normalize_dax(a_m.get("formatted_expression", ""))
        b_norm = _normalize_dax(b_m.get("formatted_expression", ""))
        if a_norm != b_norm:
            changes["formatted_expression"] = {
                "old": a_m.get("formatted_expression", ""),
                "new": b_m.get("formatted_expression", ""),
                "dax_change": "semantic",
            }
        elif a_m.get("formatted_expression", "") != b_m.get("formatted_expression", ""):
            changes["formatted_expression"] = {
                "old": a_m.get("formatted_expression", ""),
                "new": b_m.get("formatted_expression", ""),
                "dax_change": "cosmetic",
            }

        if changes:
            table, name = key
            modified.append({"table": table, "name": name, "changes": changes})

    return added, removed, modified


def _diff_columns(a_columns: dict, b_columns: dict) -> Tuple[list, list, list]:
    a_keys, b_keys = set(a_columns), set(b_columns)
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)

    modified = []
    for key in sorted(a_keys & b_keys):
        changes = _diff_field_changes(a_columns[key], b_columns[key], _COLUMN_FIELDS)
        if changes:
            table, name = key
            modified.append({"table": table, "name": name, "changes": changes})

    return added, removed, modified


def _diff_relationships(a_rels: dict, b_rels: dict) -> Tuple[list, list, list]:
    a_keys, b_keys = set(a_rels), set(b_rels)
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)

    modified = []
    for key in sorted(a_keys & b_keys):
        changes = _diff_field_changes(a_rels[key], b_rels[key], _RELATIONSHIP_FIELDS)
        if changes:
            from_table, from_column, to_table, to_column = key
            modified.append({
                "from_table": from_table, "from_column": from_column,
                "to_table": to_table, "to_column": to_column,
                "changes": changes,
            })

    return added, removed, modified


def diff_models(meta_a: dict, meta_b: dict) -> dict:
    a_measures, b_measures = _all_measures(meta_a), _all_measures(meta_b)
    a_columns, b_columns = _all_columns(meta_a), _all_columns(meta_b)
    a_rels, b_rels = _all_relationships(meta_a), _all_relationships(meta_b)

    measures_added, measures_removed, measures_modified = _diff_measures(a_measures, b_measures)
    columns_added, columns_removed, columns_modified = _diff_columns(a_columns, b_columns)
    relationships_added, relationships_removed, relationships_modified = \
        _diff_relationships(a_rels, b_rels)

    return {
        "a_model": meta_a.get("file_name"),
        "b_model": meta_b.get("file_name"),
        "measures_added": measures_added,
        "measures_removed": measures_removed,
        "measures_modified": measures_modified,
        "columns_added": columns_added,
        "columns_removed": columns_removed,
        "columns_modified": columns_modified,
        "relationships_added": relationships_added,
        "relationships_removed": relationships_removed,
        "relationships_modified": relationships_modified,
    }


def diff_impact(diff: dict, model_dir_a, model_dir_b, *, transitive: bool = False) -> dict:
    """
    Impact analysis on top of an already-computed diff_models() result:
    for each removed/modified measure or column, which measures depend on it.

    Removed measures/columns are looked up in model_dir_a (the OLD model) —
    those references are now broken. Modified measures/columns are looked up
    in model_dir_b (the NEW model) — those callers may now behave
    differently. Both directories must already be pbi-docs output
    (tables/*.json present).
    """
    removed_impact = []
    for table, name in diff["measures_removed"]:
        try:
            usages = resolver.find_measure_usages(model_dir_a, table, name, transitive=transitive)
        except resolver.ResolverError:
            usages = []
        removed_impact.append({"table": table, "name": name, "used_by": usages})

    modified_impact = []
    for entry in diff["measures_modified"]:
        try:
            usages = resolver.find_measure_usages(model_dir_b, entry["table"], entry["name"],
                                                   transitive=transitive)
        except resolver.ResolverError:
            usages = []
        modified_impact.append({"table": entry["table"], "name": entry["name"], "used_by": usages})

    columns_removed_impact = []
    for table, name in diff["columns_removed"]:
        try:
            usages = resolver.find_column_usages(model_dir_a, table, name, transitive=transitive)
        except resolver.ResolverError:
            usages = []
        columns_removed_impact.append({"table": table, "name": name, "used_by": usages})

    columns_modified_impact = []
    for entry in diff["columns_modified"]:
        try:
            usages = resolver.find_column_usages(model_dir_b, entry["table"], entry["name"],
                                                  transitive=transitive)
        except resolver.ResolverError:
            usages = []
        columns_modified_impact.append({"table": entry["table"], "name": entry["name"], "used_by": usages})

    return {
        "measures_removed_impact": removed_impact,
        "measures_modified_impact": modified_impact,
        "columns_removed_impact": columns_removed_impact,
        "columns_modified_impact": columns_modified_impact,
    }


def diff_with_impact(model_dir_a, model_dir_b, *, transitive: bool = False) -> dict:
    """Convenience wrapper for callers that only have two model_dir paths
    (CLI --diff-impact, MCP diff_impact tool) rather than already-loaded
    metadata dicts."""
    meta_a = resolver.load_metadata(model_dir_a)
    meta_b = resolver.load_metadata(model_dir_b)
    diff = diff_models(meta_a, meta_b)
    diff.update(diff_impact(diff, model_dir_a, model_dir_b, transitive=transitive))
    return diff
