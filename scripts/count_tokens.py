#!/usr/bin/env python3
"""
Real token counts for pbi-docs context comparisons (Condition A/B/C), via a
provider's dedicated count_tokens endpoint (no generation cost).

Not part of the pbi_extractor package: dev-only tool for the Horizonte 3 human
validation experiment (docs/human_validation_protocol.md) and future token
reports. Same treatment as Graphify (see CLAUDE.md section 3) — not added to
pyproject.toml, requires an extra pip install only if you choose to run it.

Replaces the bytes/4 approximation used in docs/token_optimization_report.md
and docs/precision_validation_report.md with an exact count for a given model.

Two providers supported via --provider (default: anthropic):
    anthropic  requires ANTHROPIC_API_KEY, `pip install anthropic`
    gemini     requires GEMINI_API_KEY, `pip install google-genai`

Note: each provider's count reflects its own tokenizer — a Gemini count is not
a substitute for a Claude count, and vice versa. See docs/token_optimization_report.md
for how the two are presented side by side.

Usage:
    python scripts/count_tokens.py [--provider anthropic|gemini] <file_or_dir> [<file_or_dir> ...]
    python scripts/count_tokens.py "files_test/Sales Sample.SemanticModel/definition/tables"
    python scripts/count_tokens.py --provider gemini "output/Sales Sample/tables"
    python scripts/count_tokens.py --provider gemini "output/Sales Sample/tables" "output/Sales Sample/relationships.json"

Model override: PBI_DOCS_TOKEN_MODEL env var (defaults per provider below).
"""

import argparse
import os
import sys
from pathlib import Path

PROVIDERS = {
    "anthropic": {
        "pip": "anthropic",
        "env": "ANTHROPIC_API_KEY",
        "default_model": "claude-sonnet-5",
    },
    "gemini": {
        "pip": "google-genai",
        "env": "GEMINI_API_KEY",
        "default_model": "gemini-2.5-flash",
    },
}


def _count_anthropic(combined: str, model: str) -> int:
    import anthropic

    client = anthropic.Anthropic()
    result = client.beta.messages.count_tokens(
        model=model,
        messages=[{"role": "user", "content": combined}],
    )
    return result.input_tokens


def _count_gemini(combined: str, model: str) -> int:
    from google import genai

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    result = client.models.count_tokens(model=model, contents=combined)
    return result.total_tokens


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

    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--provider", choices=sorted(PROVIDERS), default="anthropic")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    provider = PROVIDERS[args.provider]

    try:
        if args.provider == "anthropic":
            import anthropic  # noqa: F401
        else:
            from google import genai  # noqa: F401
    except ImportError:
        print(
            f"This script needs the '{provider['pip']}' package, not a pbi-docs dependency.\n"
            f"Run: pip install {provider['pip']}",
            file=sys.stderr,
        )
        return 1

    if not os.environ.get(provider["env"]):
        print(f"Set {provider['env']} in the environment first.", file=sys.stderr)
        return 1

    files = _iter_files(args.paths)
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

    model = os.environ.get("PBI_DOCS_TOKEN_MODEL", provider["default_model"])
    count_fn = _count_anthropic if args.provider == "anthropic" else _count_gemini
    real_tokens = count_fn(combined, model)

    print(f"Files:        {len(files)}")
    print(f"Bytes:        {total_bytes:,}")
    print(f"Real tokens:  {real_tokens:,}  (provider: {args.provider}, model: {model})")
    print(f"bytes/4 approx: {total_bytes // 4:,}  (for comparison against prior reports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
