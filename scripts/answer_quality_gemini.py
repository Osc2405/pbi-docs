#!/usr/bin/env python3
"""
Answer-quality experiment: does pbi-context's compressed context let a real LLM
answer business questions correctly, not just save tokens?

Runs the same 20-question set from docs/human_validation_protocol.md section 5
(canonical structured copy: scripts/fixtures/sales_sample_questions.json)
against the Gemini API under 3 conditions:
    A - raw TMDL          (files_test/Sales Sample.SemanticModel/definition/)
    B - pbi-context JSON      (output/Sales Sample/ - full dump)
    C - Gemini function calling against pbi_extractor.resolver (Gemini decides
        which tools to call - list_tables/get_table/get_measure/search_measures/
        search_columns/get_relationships/get_measure_dependencies/find_measure_usages)

Each question gets its own fresh API call per condition (no shared conversation
history across questions), so every row is independently gradable.

Dev-only, not part of the pbi_extractor package: same treatment as Graphify
(see CLAUDE.md section 3) - not added to pyproject.toml, requires:
    pip install google-genai
    GEMINI_API_KEY in the environment

Usage:
    python scripts/answer_quality_gemini.py [--condition a|b|c|all]
    python scripts/answer_quality_gemini.py --selftest

Output:
    scripts/fixtures/sales_sample_gemini_results.csv       (grade by hand: fill
                                                              grader_verdict with
                                                              Correcto/Parcial/
                                                              Incorrecto/NOT_FOUND,
                                                              see docs/human_validation_protocol.md
                                                              section 6 for the rubric)
    scripts/fixtures/sales_sample_gemini_transcripts.jsonl  (audit trail, esp.
                                                              which tools condition C
                                                              actually called)

Re-running with --condition a|b|c only replaces that condition's rows/transcripts,
leaving the others untouched, so grading can happen incrementally across sessions.

No LLM judge is used anywhere in this script - grading is manual, matching the
principle already established in docs/precision_validation_report.md section 2.3.
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(REPO_ROOT))  # so `from pbi_extractor import resolver` works without pip install -e .
from count_tokens import _iter_files  # noqa: E402 - dev-only script, not a package import
FIXTURES_DIR = Path(__file__).parent / "fixtures"
QUESTIONS_PATH = FIXTURES_DIR / "sales_sample_questions.json"
RESULTS_PATH = FIXTURES_DIR / "sales_sample_gemini_results.csv"
TRANSCRIPTS_PATH = FIXTURES_DIR / "sales_sample_gemini_transcripts.jsonl"

TMDL_ROOT = REPO_ROOT / "files_test" / "Sales Sample.SemanticModel" / "definition"
OUTPUT_DIR = REPO_ROOT / "output" / "Sales Sample"

CSV_FIELDS = [
    "condition", "question_id", "difficulty", "question", "reference_answer",
    "answer_given", "tool_calls", "prompt_tokens", "completion_tokens",
    "total_tokens", "grader_verdict",
]

RATE_LIMIT_SECONDS = 13  # free tier is 5 RPM on this model tier; stay under it
MAX_RETRIES = 5
DEFAULT_MODEL = "gemini-flash-lite-latest"

INSTRUCTION_STATIC = (
    "Sos un asistente que responde preguntas de negocio sobre un modelo de Power BI, "
    "usando EXCLUSIVAMENTE el contexto de abajo. No inventes nada. Si la respuesta no "
    "esta en el contexto, respondé exactamente: NOT_FOUND. Se breve y preciso, citando "
    "nombres exactos de tablas/columnas/measures tal como aparecen en el contexto."
)
INSTRUCTION_TOOLS = (
    "Sos un asistente que responde preguntas de negocio sobre un modelo de Power BI. "
    "No tenes el modelo cargado de antemano: usa las herramientas disponibles para "
    "consultarlo antes de responder. No inventes nada. Si despues de consultar no "
    "encontras la respuesta, respondé exactamente: NOT_FOUND. Se breve y preciso, "
    "citando nombres exactos tal como los devuelven las herramientas."
)


def _load_questions():
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def _build_condition_a_context() -> str:
    paths = [
        TMDL_ROOT / "database.tmdl",
        TMDL_ROOT / "model.tmdl",
        TMDL_ROOT / "relationships.tmdl",
        TMDL_ROOT / "tables",
    ]
    files = _iter_files([str(p) for p in paths])
    parts = [f"--- {f} ---\n{f.read_text(encoding='utf-8', errors='replace')}" for f in files]
    return "\n\n".join(parts)


def _build_condition_b_context() -> str:
    if not OUTPUT_DIR.exists():
        print(
            "output/Sales Sample not found. Generate it first:\n"
            '  python -m pbi_extractor.cli -i "files_test/Sales Sample.SemanticModel" -o output',
            file=sys.stderr,
        )
        raise SystemExit(1)
    paths = [OUTPUT_DIR / "index.json", OUTPUT_DIR / "tables", OUTPUT_DIR / "relationships.json"]
    files = _iter_files([str(p) for p in paths])
    parts = [f"--- {f} ---\n{f.read_text(encoding='utf-8', errors='replace')}" for f in files]
    return "\n\n".join(parts)


# --- Condition C: tool wrappers around pbi_extractor.resolver -------------

def _make_tools(model_dir: Path):
    from pbi_extractor import resolver

    def list_tables_tool(hidden: Optional[bool] = None, technical: Optional[bool] = None,
                          category: Optional[str] = None) -> dict:
        """List all tables in the model, optionally filtered by hidden/technical/category."""
        try:
            return {"results": resolver.list_tables(model_dir, hidden=hidden, technical=technical, category=category)}
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def get_table_tool(table_name: str, include_dax: bool = True) -> dict:
        """Get full detail (columns + measures) for one table by exact name."""
        try:
            return resolver.get_table(model_dir, table_name, include_dax=include_dax)
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def get_measure_tool(table_name: str, measure_name: str) -> dict:
        """Get one measure's full detail (DAX expression, format string, category) by exact table and measure name."""
        try:
            return resolver.get_measure(model_dir, table_name, measure_name)
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def search_measures_tool(query: str, category: Optional[str] = None) -> dict:
        """Case-insensitive substring search for a measure name across every table in the model."""
        try:
            return {"results": resolver.search_measures(model_dir, query, category=category)}
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def search_columns_tool(query: str, category: Optional[str] = None) -> dict:
        """Case-insensitive substring search for a column name across every table in the model."""
        try:
            return {"results": resolver.search_columns(model_dir, query, category=category)}
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def get_relationships_tool(table: Optional[str] = None) -> dict:
        """List relationships in the model, optionally filtered to one table."""
        try:
            return {"results": resolver.get_relationships(model_dir, table=table)}
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def get_measure_dependencies_tool(table_name: str, measure_name: str, transitive: bool = False) -> dict:
        """List the measures/columns a given measure references in its DAX expression."""
        try:
            return resolver.get_measure_dependencies(model_dir, table_name, measure_name, transitive=transitive)
        except resolver.ResolverError as e:
            return {"error": str(e)}

    def find_measure_usages_tool(table_name: str, measure_name: str, transitive: bool = False) -> dict:
        """List the other measures that reference a given measure in their DAX expression."""
        try:
            return {"results": resolver.find_measure_usages(model_dir, table_name, measure_name, transitive=transitive)}
        except resolver.ResolverError as e:
            return {"error": str(e)}

    return [
        list_tables_tool, get_table_tool, get_measure_tool, search_measures_tool,
        search_columns_tool, get_relationships_tool, get_measure_dependencies_tool,
        find_measure_usages_tool,
    ]


# --- Gemini call + response accounting -------------------------------------

def _retry_delay_seconds(e, default: float) -> float:
    """Extract the server-suggested retry delay (e.g. '24s') from a 429's error body, if present."""
    details = getattr(e, "details", None)
    if not isinstance(details, dict):
        return default
    for item in details.get("error", {}).get("details", []):
        if item.get("@type", "").endswith("RetryInfo"):
            raw = item.get("retryDelay", "")
            try:
                return float(raw.rstrip("s")) + 1  # small buffer over what the API asked for
            except ValueError:
                pass
    return default


def _call_gemini(client, model_name: str, contents: str, tools=None):
    from google.genai import errors, types

    config = None
    if tools:
        config = types.GenerateContentConfig(
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
        )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return client.models.generate_content(model=model_name, contents=contents, config=config)
        except errors.ClientError as e:
            if getattr(e, "code", None) == 429 and attempt < MAX_RETRIES - 1:
                last_error = e
                delay = _retry_delay_seconds(e, default=RATE_LIMIT_SECONDS * (2 ** attempt))
                print(f"  429, waiting {delay:.0f}s before retry {attempt + 2}/{MAX_RETRIES}...", file=sys.stderr)
                time.sleep(delay)
                continue
            raise
    raise last_error


def _usage(response):
    u = response.usage_metadata
    return u.prompt_token_count or 0, u.candidates_token_count or 0, u.total_token_count or 0


def _tool_call_count(response) -> int:
    history = getattr(response, "automatic_function_calling_history", None) or []
    count = 0
    for content in history:
        for part in (content.parts or []):
            if getattr(part, "function_call", None):
                count += 1
    return count


def _serialize_history(response) -> list:
    history = getattr(response, "automatic_function_calling_history", None) or []
    out = []
    for content in history:
        parts_out = []
        for part in (content.parts or []):
            if getattr(part, "text", None):
                parts_out.append({"text": part.text})
            elif getattr(part, "function_call", None):
                fc = part.function_call
                parts_out.append({"function_call": {"name": fc.name, "args": dict(fc.args or {})}})
            elif getattr(part, "function_response", None):
                fr = part.function_response
                parts_out.append({"function_response": {"name": fr.name, "response": fr.response}})
        out.append({"role": content.role, "parts": parts_out})
    out.append({"role": "model_final", "parts": [{"text": response.text}]})
    return out


# --- Condition runners -------------------------------------------------

def _run_static_condition(condition: str, client, model_name: str, questions: list, context: str):
    rows, transcripts = [], []
    for q in questions:
        prompt = f"{INSTRUCTION_STATIC}\n\nContexto:\n{context}\n\n---\n\nPregunta: {q['question']}"
        response = _call_gemini(client, model_name, prompt)
        prompt_tok, completion_tok, total_tok = _usage(response)
        rows.append({
            "condition": condition, "question_id": q["id"], "difficulty": q["difficulty"],
            "question": q["question"], "reference_answer": q["reference_answer"],
            "answer_given": response.text, "tool_calls": 0,
            "prompt_tokens": prompt_tok, "completion_tokens": completion_tok,
            "total_tokens": total_tok, "grader_verdict": "",
        })
        transcripts.append({
            "condition": condition, "question_id": q["id"],
            "transcript": [{"role": "user", "parts": [{"text": f"Pregunta: {q['question']}"}]}],
        })
        time.sleep(RATE_LIMIT_SECONDS)
    return rows, transcripts


def run_condition_a(client, model_name, questions):
    return _run_static_condition("a", client, model_name, questions, _build_condition_a_context())


def run_condition_b(client, model_name, questions):
    return _run_static_condition("b", client, model_name, questions, _build_condition_b_context())


def run_condition_c(client, model_name, questions):
    if not OUTPUT_DIR.exists():
        print(
            "output/Sales Sample not found. Generate it first:\n"
            '  python -m pbi_extractor.cli -i "files_test/Sales Sample.SemanticModel" -o output',
            file=sys.stderr,
        )
        raise SystemExit(1)

    tools = _make_tools(OUTPUT_DIR)
    rows, transcripts = [], []
    for q in questions:
        prompt = f"{INSTRUCTION_TOOLS}\n\nPregunta: {q['question']}"
        response = _call_gemini(client, model_name, prompt, tools=tools)
        prompt_tok, completion_tok, total_tok = _usage(response)
        tool_calls = _tool_call_count(response)
        rows.append({
            "condition": "c", "question_id": q["id"], "difficulty": q["difficulty"],
            "question": q["question"], "reference_answer": q["reference_answer"],
            "answer_given": response.text, "tool_calls": tool_calls,
            "prompt_tokens": prompt_tok, "completion_tokens": completion_tok,
            "total_tokens": total_tok, "grader_verdict": "",
        })
        transcripts.append({
            "condition": "c", "question_id": q["id"],
            "transcript": _serialize_history(response),
        })
        time.sleep(RATE_LIMIT_SECONDS)
    return rows, transcripts


# --- CSV / JSONL merge (condition-scoped rerun) -----------------------

def _read_csv_rows(path: Path) -> list:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv_rows(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _read_jsonl_rows(path: Path) -> list:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl_rows(path: Path, rows: list):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _merge_rows(existing: list, new: list, conditions_run: list) -> list:
    """Replace rows belonging to conditions_run with new rows, keep the rest untouched."""
    kept = [r for r in existing if r.get("condition") not in conditions_run]
    merged = kept + new
    merged.sort(key=lambda r: (r["condition"], int(r["question_id"])))
    return merged


def _selftest():
    existing = [
        {"condition": "a", "question_id": 1, "grader_verdict": "Correcto"},
        {"condition": "a", "question_id": 2, "grader_verdict": "Incorrecto"},
        {"condition": "b", "question_id": 1, "grader_verdict": "Correcto"},
    ]
    new_a = [
        {"condition": "a", "question_id": 1, "grader_verdict": ""},
        {"condition": "a", "question_id": 2, "grader_verdict": ""},
    ]
    merged = _merge_rows(existing, new_a, ["a"])
    assert len(merged) == 3, merged
    assert [r for r in merged if r["condition"] == "b"][0]["grader_verdict"] == "Correcto"
    assert all(r["grader_verdict"] == "" for r in merged if r["condition"] == "a")

    new_c = [{"condition": "c", "question_id": 1, "grader_verdict": ""}]
    merged2 = _merge_rows(merged, new_c, ["c"])
    assert len(merged2) == 4, merged2
    assert merged2[0]["condition"] == "a" and merged2[-1]["condition"] == "c"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--condition", choices=["a", "b", "c", "all"], default="all")
    parser.add_argument("--selftest", action="store_true", help="run offline self-check, no API key needed")
    args = parser.parse_args()

    if args.selftest:
        _selftest()
        print("selftest OK")
        return 0

    try:
        from google import genai
    except ImportError:
        print(
            "This script needs the 'google-genai' package, not a pbi-context dependency.\n"
            "Run: pip install google-genai",
            file=sys.stderr,
        )
        return 1

    if not os.environ.get("GEMINI_API_KEY"):
        print("Set GEMINI_API_KEY in the environment first.", file=sys.stderr)
        return 1

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_name = os.environ.get("PBI_DOCS_GEMINI_MODEL", DEFAULT_MODEL)
    questions = _load_questions()

    conditions_to_run = ["a", "b", "c"] if args.condition == "all" else [args.condition]
    runners = {"a": run_condition_a, "b": run_condition_b, "c": run_condition_c}

    new_csv_rows, new_transcript_rows = [], []
    for cond in conditions_to_run:
        print(f"Running condition {cond}...")
        rows, transcripts = runners[cond](client, model_name, questions)
        new_csv_rows.extend(rows)
        new_transcript_rows.extend(transcripts)

    merged_csv = _merge_rows(_read_csv_rows(RESULTS_PATH), new_csv_rows, conditions_to_run)
    _write_csv_rows(RESULTS_PATH, merged_csv)

    merged_transcripts = _merge_rows(_read_jsonl_rows(TRANSCRIPTS_PATH), new_transcript_rows, conditions_to_run)
    _write_jsonl_rows(TRANSCRIPTS_PATH, merged_transcripts)

    print(f"Wrote {len(new_csv_rows)} rows to {RESULTS_PATH}")
    print(f"Wrote transcripts to {TRANSCRIPTS_PATH}")
    print("Next: open the CSV and fill grader_verdict by hand (Correcto/Parcial/Incorrecto/NOT_FOUND).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
