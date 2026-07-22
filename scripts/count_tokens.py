#!/usr/bin/env python3
"""
Real token counts for pbi-docs context comparisons (Condition A/B/C), via the
Anthropic API's count_tokens endpoint.

Not part of the pbi_extractor package: dev-only tool for the Horizonte 3 human
validation experiment (docs/human_validation_protocol.md) and future token
reports. Same treatment as Graphify (see CLAUDE.md section 3) — not added to
pyproject.toml, requires `pip install anthropic` only if you choose to run it.

Replaces the bytes/4 approximation used in docs/token_optimization_report.md
and docs/precision_validation_report.md with an exact count for a given model.

Usage:
    python scripts/count_tokens.py <file_or_dir> [<file_or_dir> ...]
    python scripts/count_tokens.py "files_test/Sales Sample.SemanticModel/definition/tables"
    python scripts/count_tokens.py "output/Sales Sample/tables"
    python scripts/count_tokens.py "output/Sales Sample/tables" "output/Sales Sample/relationships.json"

Requires ANTHROPIC_API_KEY in the environment.
"""

import os
import sys
from pathlib import Path


def _iter_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(f for f in p.rglob("*") if f.is_file()))
        elif p.is_file():
            files.append(p)
        else:
            raise FileNotFoundError(f"Not found: {raw}")
    return files


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    try:
        import anthropic
    except ImportError:
        print(
            "This script needs the 'anthropic' package, not a pbi-docs dependency.\n"
            "Run: pip install anthropic",
            file=sys.stderr,
        )
        return 1

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Set ANTHROPIC_API_KEY in the environment first.", file=sys.stderr)
        return 1

    files = _iter_files(sys.argv[1:])
    if not files:
        print("No files found under the given paths.", file=sys.stderr)
        return 1

    parts = []
    total_bytes = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        total_bytes += len(text.encode("utf-8"))
        parts.append(f"--- {f} ---\n{text}")
    combined = "\n\n".join(parts)

    client = anthropic.Anthropic()
    model = os.environ.get("PBI_DOCS_TOKEN_MODEL", "claude-sonnet-5")
    result = client.beta.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": combined}],
    )

    print(f"Files:        {len(files)}")
    print(f"Bytes:        {total_bytes:,}")
    print(f"Real tokens:  {result.input_tokens:,}  (model: {model})")
    print(f"bytes/4 approx: {total_bytes // 4:,}  (for comparison against prior reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
