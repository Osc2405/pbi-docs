"""Tests for pbi_extractor.resolver — query layer over an already-processed output dir."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from pbi_extractor.cli import process_file
from pbi_extractor.resolver import (
    list_tables,
    get_table,
    get_measure,
    get_relationships,
    search_measures,
    search_columns,
    get_measure_dependencies,
    find_measure_usages,
    load_metadata,
    ResolverError,
)

FIXTURE = Path(__file__).parent / "fixtures" / "minimal_pbip" / "my-model.pbip"

# Real Microsoft sample (files_test/, not tests/fixtures/) — used only for the
# transitive-dependency tests below, which need a 3+ level measure chain that
# doesn't exist in the small synthetic minimal_pbip fixture.
SALES_SAMPLE_FIXTURE = Path(__file__).parent.parent / "files_test" / "Sales Sample.pbip"

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import generate_synthetic_pbip  # noqa: E402 — dev-only script, not a package import


@pytest.fixture(scope="module")
def json_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("resolver_json")
    process_file(FIXTURE, out, index_format="json")
    return out / "my-model"


@pytest.fixture(scope="module")
def toon_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("resolver_toon")
    process_file(FIXTURE, out, index_format="toon")
    return out / "my-model"


@pytest.fixture(scope="module")
def sales_sample_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("resolver_sales_sample")
    process_file(SALES_SAMPLE_FIXTURE, out, index_format="json")
    return out / "Sales Sample"


@pytest.fixture(scope="module")
def large_synthetic_dir(tmp_path_factory):
    """60-table/288-measure synthetic model (docs/scale_validation_report.md) —
    used only for the transitive-usages perf regression test below."""
    src = tmp_path_factory.mktemp("synthetic_src")
    generate_synthetic_pbip.generate(src, num_dims=20, num_facts=40)
    out = tmp_path_factory.mktemp("resolver_large_synthetic")
    process_file(src, out, index_format="auto")
    return out / generate_synthetic_pbip.MODEL_NAME


# ---------------------------------------------------------------------------
# list_tables
# ---------------------------------------------------------------------------

def test_list_tables_all(json_dir):
    tables = list_tables(json_dir)
    names = {t["name"] for t in tables}
    assert names == {"Sales", "Date", "_Measures"}


def test_list_tables_filter_hidden(json_dir):
    hidden = list_tables(json_dir, hidden=True)
    assert {t["name"] for t in hidden} == {"Date", "_Measures"}


def test_list_tables_filter_category(json_dir):
    tables = list_tables(json_dir, category="revenue")
    assert {t["name"] for t in tables} == {"Sales"}


# ---------------------------------------------------------------------------
# get_table — parity between JSON-sourced and TOON-sourced output
# ---------------------------------------------------------------------------

def test_get_table_json_toon_parity(json_dir, toon_dir):
    """The whole point of the resolver: identical shape regardless of source format."""
    from_json = get_table(json_dir, "Sales")
    from_toon = get_table(toon_dir, "Sales")
    assert from_json == from_toon


def test_get_table_measure_shape(json_dir):
    table = get_table(json_dir, "Sales")
    names = {m["name"] for m in table["measures"]}
    assert names == {"Total Sales", "YTD Sales"}
    m = next(m for m in table["measures"] if m["name"] == "Total Sales")
    assert set(m.keys()) == {
        "name", "category", "complexity", "is_hidden",
        "format_string", "display_folder", "formatted_expression",
    }
    assert "SUM(Sales[SalesAmount])" in m["formatted_expression"]


def test_get_table_include_dax_false(json_dir):
    table = get_table(json_dir, "Sales", include_dax=False)
    assert all("formatted_expression" not in m for m in table["measures"])


def test_get_table_unknown_raises(json_dir):
    with pytest.raises(ResolverError, match="Unknown table") as exc_info:
        get_table(json_dir, "DoesNotExist")
    assert "Sales" in str(exc_info.value)  # fallback to index.json still lists available tables


def test_get_table_does_not_load_index_on_happy_path(json_dir, monkeypatch):
    """Regression test for the scale-validation fix (docs/scale_validation_report.md
    section 4): a point lookup for a table that's already known by name must not
    pay index.json's fixed cost — the filename is fully determined by
    _safe_filename(table_name), so index.json should only be read on the
    not-found fallback path."""
    import pbi_extractor.resolver as resolver_module

    def _boom(model_dir):
        raise AssertionError("load_index() was called on the get_table() happy path")

    monkeypatch.setattr(resolver_module, "load_index", _boom)
    table = get_table(json_dir, "Sales")
    assert table["name"] == "Sales"


def test_get_measure_does_not_load_index_on_happy_path(json_dir, monkeypatch):
    """get_measure() delegates to get_table(), so it inherits the same fix."""
    import pbi_extractor.resolver as resolver_module

    def _boom(model_dir):
        raise AssertionError("load_index() was called on the get_measure() happy path")

    monkeypatch.setattr(resolver_module, "load_index", _boom)
    m = get_measure(json_dir, "Sales", "Total Sales")
    assert m["name"] == "Total Sales"


# ---------------------------------------------------------------------------
# get_relationships
# ---------------------------------------------------------------------------

def test_get_relationships_all(json_dir):
    rels = get_relationships(json_dir)
    assert len(rels) == 2


def test_get_relationships_filter_by_table(json_dir):
    rels = get_relationships(json_dir, table="Date")
    assert len(rels) == 1
    assert rels[0]["to_table"] == "Date"


def test_get_relationships_toon_parity(json_dir, toon_dir):
    """TOON relationships intentionally omit `name` (CLAUDE.md's TOON field scope excludes
    it — often just an auto-generated GUID). Compare the fields TOON actually carries."""
    shared_fields = ["from_table", "from_column", "to_table", "to_column",
                      "cardinality", "cross_filtering", "is_active"]
    from_json = [{k: r[k] for k in shared_fields} for r in get_relationships(json_dir)]
    from_toon = [{k: r[k] for k in shared_fields} for r in get_relationships(toon_dir)]
    assert from_json == from_toon


# ---------------------------------------------------------------------------
# search_measures
# ---------------------------------------------------------------------------

def test_search_measures_by_substring(json_dir):
    results = search_measures(json_dir, "sales")
    names = {r["name"] for r in results}
    assert "Total Sales" in names
    assert "YTD Sales" in names
    assert all(r["table"] == "Sales" for r in results)


def test_search_measures_cross_table(json_dir):
    results = search_measures(json_dir, "KPI")
    assert any(r["table"] == "_Measures" for r in results)


def test_search_measures_no_match(json_dir):
    assert search_measures(json_dir, "nonexistent-xyz") == []


# ---------------------------------------------------------------------------
# get_measure
# ---------------------------------------------------------------------------

def test_get_measure(json_dir):
    m = get_measure(json_dir, "Sales", "Total Sales")
    assert m["table"] == "Sales"
    assert "SUM(Sales[SalesAmount])" in m["formatted_expression"]


def test_get_measure_json_toon_parity(json_dir, toon_dir):
    assert get_measure(json_dir, "Sales", "Total Sales") == get_measure(toon_dir, "Sales", "Total Sales")


def test_get_measure_unknown_raises(json_dir):
    with pytest.raises(ResolverError, match="Unknown measure"):
        get_measure(json_dir, "Sales", "Nope")


# ---------------------------------------------------------------------------
# search_columns
# ---------------------------------------------------------------------------

def test_search_columns_by_substring(json_dir):
    results = search_columns(json_dir, "sales")
    names = {r["name"] for r in results}
    assert "SalesID" in names
    assert "SalesAmount" in names
    assert all(r["table"] == "Sales" for r in results)


def test_search_columns_no_match(json_dir):
    assert search_columns(json_dir, "nonexistent-xyz") == []


# ---------------------------------------------------------------------------
# get_measure_dependencies / find_measure_usages
# ---------------------------------------------------------------------------
# 'YTD Sales' = CALCULATE([Total Sales], DATESYTD('Date'[Date])) — references
# the 'Total Sales' measure and the Date[Date] column.

def test_get_measure_dependencies_measures_and_columns(json_dir):
    deps = get_measure_dependencies(json_dir, "Sales", "YTD Sales")
    assert deps["table"] == "Sales"
    assert deps["measure"] == "YTD Sales"
    assert deps["references_measures"] == ["Total Sales"]
    assert deps["references_columns"] == [{"table": "Date", "column": "Date"}]


def test_get_measure_dependencies_column_only(json_dir):
    """'Total Sales' = SUM(Sales[SalesAmount]) — references a column, no other measure."""
    deps = get_measure_dependencies(json_dir, "Sales", "Total Sales")
    assert deps["references_measures"] == []
    assert deps["references_columns"] == [{"table": "Sales", "column": "SalesAmount"}]


def test_get_measure_dependencies_unknown_raises(json_dir):
    with pytest.raises(ResolverError, match="Unknown measure"):
        get_measure_dependencies(json_dir, "Sales", "Nope")


def test_extract_references_bare_bracket_matching_own_column_is_a_column(json_dir):
    """Regression test: a bare `[X]` (no table qualifier) is ambiguous DAX —
    it can mean a measure OR an unqualified reference to a column of the same
    table the expression lives on, e.g. `SUM([Value])` inside a Fact measure
    meaning Fact[Value]. Found validating against a real-world model
    (Corporate Spend) where this was wrongly bucketed into
    references_measures instead of references_columns — see CHANGELOG."""
    from pbi_extractor.resolver import _extract_references

    refs = _extract_references(
        "SUM([Value])", own_table="Fact", own_columns={"Value", "Date"}
    )
    assert refs["measures"] == []
    assert refs["columns"] == [{"table": "Fact", "column": "Value"}]


def test_extract_references_bare_bracket_not_matching_own_column_is_a_measure(json_dir):
    """Same bare-bracket syntax, but 'Amount' isn't a column of Fact — still a
    measure reference, exactly as before the fix."""
    from pbi_extractor.resolver import _extract_references

    refs = _extract_references(
        "CALCULATE([Amount], Scenario[ScenarioDescription]=\"Actual\")",
        own_table="Fact", own_columns={"Value", "Date"},
    )
    assert refs["measures"] == ["Amount"]
    assert refs["columns"] == [{"table": "Scenario", "column": "ScenarioDescription"}]


def test_find_measure_usages_direct_reference(json_dir):
    """'Total Sales' is referenced by 'YTD Sales' (Sales) and 'Complex KPI'
    (_Measures, twice in its expression — must be deduped to one entry)."""
    usages = find_measure_usages(json_dir, "Sales", "Total Sales")
    assert {(u["table"], u["name"]) for u in usages} == {
        ("Sales", "YTD Sales"),
        ("_Measures", "Complex KPI"),
    }
    assert len(usages) == 2  # dedup: 'Complex KPI' references [Total Sales] twice


def test_find_measure_usages_no_usages(json_dir):
    assert find_measure_usages(json_dir, "Sales", "YTD Sales") == []


def test_find_measure_usages_excludes_self(json_dir):
    usages = find_measure_usages(json_dir, "Sales", "Total Sales")
    assert not any(u["table"] == "Sales" and u["name"] == "Total Sales" for u in usages)


def test_dependencies_json_toon_parity(json_dir, toon_dir):
    assert (get_measure_dependencies(json_dir, "Sales", "YTD Sales")
            == get_measure_dependencies(toon_dir, "Sales", "YTD Sales"))


def test_dependencies_transitive_default_false_unchanged(json_dir):
    """transitive=False (default) must return exactly what it always has — no new keys."""
    assert (get_measure_dependencies(json_dir, "Sales", "YTD Sales")
            == get_measure_dependencies(json_dir, "Sales", "YTD Sales", transitive=False))


def test_usages_transitive_default_false_unchanged(json_dir):
    assert (find_measure_usages(json_dir, "Sales", "Total Sales")
            == find_measure_usages(json_dir, "Sales", "Total Sales", transitive=False))


# ---------------------------------------------------------------------------
# Transitive dependencies/usages — needs a 3+ level chain, not present in the
# small synthetic fixture, so these use the real Sales Sample model.
# Margin % Overall -> Margin % -> {Margin, Sales Amount}
# ---------------------------------------------------------------------------

def test_get_measure_dependencies_transitive_three_levels(sales_sample_dir):
    deps = get_measure_dependencies(sales_sample_dir, "Sales", "Margin % Overall", transitive=True)
    assert deps["transitive"] is True
    assert deps["references_measures"] == ["Margin", "Margin %", "Sales Amount"]
    assert {(c["table"], c["column"]) for c in deps["references_columns"]} == {
        ("Sales", "Quantity"), ("Sales", "Net Price"), ("Sales", "Unit Cost"),
    }


def test_get_measure_dependencies_transitive_excludes_self(sales_sample_dir):
    deps = get_measure_dependencies(sales_sample_dir, "Sales", "Margin % Overall", transitive=True)
    assert "Margin % Overall" not in deps["references_measures"]


def test_get_measure_dependencies_non_transitive_stops_at_one_level(sales_sample_dir):
    """Same measure, transitive=False: only 'Margin %', not its own dependencies."""
    deps = get_measure_dependencies(sales_sample_dir, "Sales", "Margin % Overall")
    assert deps["references_measures"] == ["Margin %"]
    assert "transitive" not in deps


def test_find_measure_usages_transitive_three_levels(sales_sample_dir):
    """Inverse of the chain above: Sales Amount is used (directly or indirectly)
    by Margin %, which is used by Margin % Overall."""
    usages = find_measure_usages(sales_sample_dir, "Sales", "Sales Amount", transitive=True)
    names = {(u["table"], u["name"]) for u in usages}
    assert ("Sales", "Margin %") in names
    assert ("Sales", "Margin % Overall") in names


def test_find_measure_usages_non_transitive_excludes_indirect(sales_sample_dir):
    """Margin % Overall only shows up transitively, not in the direct (one-hop) usages."""
    usages = find_measure_usages(sales_sample_dir, "Sales", "Sales Amount")
    names = {(u["table"], u["name"]) for u in usages}
    assert ("Sales", "Margin % Overall") not in names


def test_find_measure_usages_transitive_reads_model_once_not_per_hop(large_synthetic_dir, monkeypatch):
    """Regression guard for the perf fix in docs/scale_validation_report.md section 5:
    before the fix, every BFS hop called _all_measures() (a fresh read+parse of
    every table file) instead of reusing one cached pass — O(hops x tables)
    instead of O(tables). Asserting the call count directly instead of timing
    it, which was flaky across cold/warm filesystem cache."""
    import pbi_extractor.resolver as resolver_module

    real_all_measures = resolver_module._all_measures
    call_count = {"n": 0}

    def _counting_all_measures(model_dir):
        call_count["n"] += 1
        return real_all_measures(model_dir)

    monkeypatch.setattr(resolver_module, "_all_measures", _counting_all_measures)

    # Fact01 (not the first table alphabetically — dimension tables carry no
    # measures in this synthetic model).
    detail = get_table(large_synthetic_dir, "Fact01")
    measure_name = detail["measures"][0]["name"]

    find_measure_usages(large_synthetic_dir, "Fact01", measure_name, transitive=True)

    assert call_count["n"] == 1, (
        f"_all_measures() was called {call_count['n']} times during one transitive "
        "walk — expected exactly 1 (cached across all BFS hops), not re-read per hop"
    )


# ---------------------------------------------------------------------------
# CLI --query dispatch
# ---------------------------------------------------------------------------

def _run_cli(*args):
    result = subprocess.run(
        [sys.executable, "-m", "pbi_extractor.cli", *args],
        cwd=Path(__file__).parent.parent,
        capture_output=True, text=True,
    )
    return result


def test_cli_query_list_tables(json_dir):
    result = _run_cli("--query", str(json_dir), "--list-tables")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert {t["name"] for t in payload} == {"Sales", "Date", "_Measures"}


def test_cli_query_table(json_dir):
    result = _run_cli("--query", str(json_dir), "--table", "Sales")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == get_table(json_dir, "Sales")


def test_cli_query_search_measures(json_dir):
    result = _run_cli("--query", str(json_dir), "--search-measures", "sales")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 2


def test_cli_query_relationships_filtered(json_dir):
    result = _run_cli("--query", str(json_dir), "--relationships", "--table", "Date")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert len(payload) == 1


def test_cli_query_measure(json_dir):
    result = _run_cli("--query", str(json_dir), "--table", "Sales", "--measure", "Total Sales")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == get_measure(json_dir, "Sales", "Total Sales")


def test_cli_query_search_columns(json_dir):
    result = _run_cli("--query", str(json_dir), "--search-columns", "sales")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == search_columns(json_dir, "sales")


def test_cli_query_unknown_table_exits_nonzero(json_dir):
    result = _run_cli("--query", str(json_dir), "--table", "Nope")
    assert result.returncode == 1


def test_cli_query_dependencies(json_dir):
    result = _run_cli("--query", str(json_dir), "--table", "Sales",
                       "--measure", "YTD Sales", "--dependencies")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == get_measure_dependencies(json_dir, "Sales", "YTD Sales")


def test_cli_query_usages(json_dir):
    result = _run_cli("--query", str(json_dir), "--table", "Sales",
                       "--measure", "Total Sales", "--usages")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == find_measure_usages(json_dir, "Sales", "Total Sales")


# ---------------------------------------------------------------------------
# load_metadata — used by diff.py's model_dir-based wrappers (diff_with_impact)
# ---------------------------------------------------------------------------

def test_load_metadata_returns_full_dict(json_dir):
    meta = load_metadata(json_dir)
    assert meta["summary"]["total_tables"] > 0
    with open(json_dir / "metadata.json", "r", encoding="utf-8") as f:
        assert meta == json.load(f)


def test_load_metadata_missing_file_raises_resolver_error(tmp_path):
    with pytest.raises(ResolverError):
        load_metadata(tmp_path)
