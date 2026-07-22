"""
TOON — Token-Oriented Object Notation encoder/decoder.

Reduces token consumption ~30-60% for uniform arrays by declaring
field names once and storing data as rows (similar to CSV embedded in JSON).

Format:
    {
        "__toon": true,
        "__fields": ["field1", "field2", ...],
        "__rows": [
            [value1, value2, ...],
            ...
        ]
    }

Apply ONLY to uniform arrays (columns, relationships, flat measures).
Never apply to DAX expressions, free-text fields, or nested/variable structures.
"""

from typing import Any, List


def encode_toon(records: List[dict], fields: List[str]) -> dict:
    """
    Convert a list of uniform dicts to TOON format.

    Args:
        records: List of dicts that all share the same fields.
        fields: Ordered list of field names to include (defines column order).

    Returns:
        TOON block dict with __toon, __fields, __rows.
    """
    return {
        "__toon": True,
        "__fields": list(fields),
        "__rows": [
            [record.get(field) for field in fields]
            for record in records
        ],
    }


def decode_toon(toon_block: dict) -> List[dict]:
    """
    Convert a TOON block back to a list of dicts.

    Args:
        toon_block: Dict produced by encode_toon().

    Returns:
        List of dicts reconstructed from the TOON rows.

    Raises:
        KeyError: If __fields or __rows are missing.
    """
    fields = toon_block["__fields"]
    return [dict(zip(fields, row)) for row in toon_block["__rows"]]
