"""
Utilities for comparing two models (cleaned_metadata) and producing a simple diff.
"""

from typing import Dict, Set, Tuple


def _measure_set(meta: dict) -> Set[Tuple[str, str]]:
    items = set()
    for t in meta.get("tables", []):
        for m in t.get("measures", []):
            items.add((t.get("name", "?"), m.get("name", "?")))
    return items


def _rel_set(meta: dict) -> Set[Tuple[str, str, str, str, str, str]]:
    items = set()
    for r in meta.get("relationships", []):
        items.add(
            (
                r.get("from_table", ""),
                r.get("from_column", ""),
                r.get("to_table", ""),
                r.get("to_column", ""),
                r.get("cardinality", ""),
                r.get("cross_filtering", ""),
            )
        )
    return items


def diff_models(meta_a: dict, meta_b: dict) -> dict:
    a_measures, b_measures = _measure_set(meta_a), _measure_set(meta_b)
    a_rels, b_rels = _rel_set(meta_a), _rel_set(meta_b)
    return {
        "a_model": meta_a.get("file_name"),
        "b_model": meta_b.get("file_name"),
        "measures_added": sorted(list(b_measures - a_measures)),
        "measures_removed": sorted(list(a_measures - b_measures)),
        "relationships_added": sorted(list(b_rels - a_rels)),
        "relationships_removed": sorted(list(a_rels - b_rels)),
    }
