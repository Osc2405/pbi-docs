#!/usr/bin/env python3
"""
Generate a synthetic, large PBIP/TMDL project for scale validation
(Fase 0 of the context/audit-layer roadmap).

Not part of the pbi_extractor package: dev-only tool, same treatment as
scripts/count_tokens.py and Graphify (CLAUDE.md section 3) — not added to
pyproject.toml, zero extra dependencies.

Why synthetic: no free/public PBIP project at enterprise scale could be found
(checked microsoft/powerbi-desktop-samples, microsoft/Analysis-Services,
microsoft/fabric-samples, and several community repos — all converge on the
same ~10-table teaching model already in files_test/Sales Sample, since PBIP
is a recent format and the classic large sample databases only exist as
.bak/.bim/.pbix, not as TMDL folders). This generator produces a star-schema
model at a scale no public sample currently offers, purely to measure
pbi-context's own behavior (timing, index.json size, TOON threshold) — it says
nothing about parsing real-world DAX authoring quirks, which is what an
actual production model would exercise instead.

Usage:
    python scripts/generate_synthetic_pbip.py <output_dir> [--dims N] [--facts N]
    python scripts/generate_synthetic_pbip.py "C:/tmp/big-model" --dims 20 --facts 40
"""

import argparse
import random
from pathlib import Path

MODEL_NAME = "SyntheticLarge"

_DIM_ATTR_TYPES = ["string", "int64", "dateTime", "decimal", "boolean"]

_MEASURE_TEMPLATES = [
    ("Total {col}", "SUM({table}[{col}])"),
    ("Avg {col}", "AVERAGE({table}[{col}])"),
    ("Count {col}", "COUNTROWS({table})"),
    ("YTD {col}", "CALCULATE([Total {col}], DATESYTD({date_col}))"),
    ("{col} vs Prior Year", "VAR CurrentValue = [Total {col}]\n"
                            "VAR PriorValue = CALCULATE([Total {col}], SAMEPERIODLASTYEAR({date_col}))\n"
                            "RETURN\n\tDIVIDE(CurrentValue - PriorValue, PriorValue)"),
    ("Filtered {col}", "CALCULATE([Total {col}], FILTER({table}, {table}[{col}] > 0))"),
]


def _tabs(n: int) -> str:
    return "\t" * n


def _dim_table_tmdl(name: str, num_attrs: int) -> str:
    lines = [f"table {name}", ""]
    lines.append(f"{_tabs(1)}column {name}_Key")
    lines.append(f"{_tabs(2)}dataType: int64")
    lines.append(f"{_tabs(2)}sourceColumn: {name}_Key")
    lines.append("")
    for i in range(num_attrs):
        col = f"Attribute{i + 1}"
        dtype = _DIM_ATTR_TYPES[i % len(_DIM_ATTR_TYPES)]
        lines.append(f"{_tabs(1)}column {col}")
        lines.append(f"{_tabs(2)}dataType: {dtype}")
        if i % 5 == 0 and i > 0:
            lines.append(f"{_tabs(2)}isHidden")
        lines.append(f"{_tabs(2)}sourceColumn: {col}")
        lines.append("")
    lines.append(f"{_tabs(1)}partition {name}-Partition")
    lines.append(f"{_tabs(2)}mode: import")
    lines.append(f"{_tabs(2)}source")
    lines.append(f"{_tabs(3)}type: m")
    lines.append("")
    return "\n".join(lines)


def _fact_table_tmdl(name: str, fk_dims: list, num_numeric_cols: int,
                      num_measures: int, rng: random.Random) -> str:
    lines = [f"table {name}", ""]
    lines.append(f"{_tabs(1)}column {name}_Key")
    lines.append(f"{_tabs(2)}dataType: int64")
    lines.append(f"{_tabs(2)}sourceColumn: {name}_Key")
    lines.append("")
    lines.append(f"{_tabs(1)}column DateKey")
    lines.append(f"{_tabs(2)}dataType: dateTime")
    lines.append(f"{_tabs(2)}formatString: yyyy-mm-dd")
    lines.append(f"{_tabs(2)}sourceColumn: DateKey")
    lines.append("")
    for dim in fk_dims:
        col = f"{dim}_Key"
        lines.append(f"{_tabs(1)}column {col}")
        lines.append(f"{_tabs(2)}dataType: int64")
        lines.append(f"{_tabs(2)}sourceColumn: {col}")
        lines.append("")

    numeric_cols = []
    for i in range(num_numeric_cols):
        # Prefixed with the table name: measure names are derived from these
        # column names below, and DAX measure names must be unique model-wide
        # (a real Tabular model rejects duplicates) — a bare "Amount1" would
        # collide across all 40 fact tables and inflate the dependency graph
        # with cross-table name collisions that couldn't exist in a real model.
        col = f"{name}Amount{i + 1}"
        numeric_cols.append(col)
        lines.append(f"{_tabs(1)}column {col}")
        lines.append(f"{_tabs(2)}dataType: decimal")
        lines.append(f"{_tabs(2)}formatString: $#,0.###")
        lines.append(f"{_tabs(2)}sourceColumn: {col}")
        lines.append("")

    measure_names = []
    for i in range(num_measures):
        template_name, template_expr = _MEASURE_TEMPLATES[i % len(_MEASURE_TEMPLATES)]
        col = numeric_cols[i % len(numeric_cols)]
        m_name = template_name.format(col=col)
        # avoid duplicate names when num_measures > distinct (col, template) combos
        if m_name in measure_names:
            m_name = f"{m_name} {i}"
        measure_names.append(m_name)
        expr = template_expr.format(table=name, col=col, date_col=f"{name}[DateKey]")

        lines.append(f"{_tabs(1)}measure '{m_name}' =")
        for expr_line in expr.split("\n"):
            lines.append(f"{_tabs(2)}{expr_line}")
        lines.append(f"{_tabs(2)}formatString: $#,0")
        if i % 4 == 0:
            lines.append(f"{_tabs(2)}displayFolder: Calculations")
        lines.append("")

    lines.append(f"{_tabs(1)}partition {name}-Partition")
    lines.append(f"{_tabs(2)}mode: import")
    lines.append(f"{_tabs(2)}source")
    lines.append(f"{_tabs(3)}type: m")
    lines.append("")
    return "\n".join(lines)


def generate(output_dir: Path, num_dims: int, num_facts: int, seed: int = 42) -> dict:
    rng = random.Random(seed)

    sm_dir = output_dir / f"{MODEL_NAME}.SemanticModel"
    definition_dir = sm_dir / "definition"
    tables_dir = definition_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / f"{MODEL_NAME}.pbip").write_text(
        f'{{\n  "version": "1.0",\n  "artifacts": [\n    {{\n      "dataset": {{\n'
        f'        "path": "{MODEL_NAME}.SemanticModel"\n      }}\n    }}\n  ],\n'
        f'  "settings": {{\n    "enableAutoRecovery": true\n  }}\n}}\n',
        encoding="utf-8",
    )

    (definition_dir / "database.tmdl").write_text(
        f"database {MODEL_NAME}\n\tcompatibilityLevel: 1604\n", encoding="utf-8"
    )
    (definition_dir / "model.tmdl").write_text(
        "model Model\n\tculture: en-US\n", encoding="utf-8"
    )

    dim_names = [f"Dim{i + 1:02d}" for i in range(num_dims)]
    for dim in dim_names:
        num_attrs = rng.randint(8, 14)
        (tables_dir / f"{dim}.tmdl").write_text(
            _dim_table_tmdl(dim, num_attrs), encoding="utf-8"
        )

    fact_names = [f"Fact{i + 1:02d}" for i in range(num_facts)]
    relationships = []
    for fact in fact_names:
        fk_dims = rng.sample(dim_names, k=min(3, len(dim_names)))
        num_numeric = rng.randint(4, 8)
        num_measures = rng.randint(5, 10)
        (tables_dir / f"{fact}.tmdl").write_text(
            _fact_table_tmdl(fact, fk_dims, num_numeric, num_measures, rng),
            encoding="utf-8",
        )
        for dim in fk_dims:
            relationships.append((fact, dim))

    rel_lines = []
    for fact, dim in relationships:
        rel_lines.append(f"relationship Rel_{fact}_{dim}")
        rel_lines.append(f"{_tabs(1)}fromColumn: {fact}.{dim}_Key")
        rel_lines.append(f"{_tabs(1)}toColumn: {dim}.{dim}_Key")
        rel_lines.append(f"{_tabs(1)}fromCardinality: many")
        rel_lines.append(f"{_tabs(1)}toCardinality: one")
        rel_lines.append("")
    (definition_dir / "relationships.tmdl").write_text(
        "\n".join(rel_lines), encoding="utf-8"
    )

    return {
        "output_dir": str(output_dir),
        "num_tables": num_dims + num_facts,
        "num_dims": num_dims,
        "num_facts": num_facts,
        "num_relationships": len(relationships),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("output_dir", type=Path, help="Directory to write the PBIP project into")
    parser.add_argument("--dims", type=int, default=20, help="Number of dimension tables (default 20)")
    parser.add_argument("--facts", type=int, default=40, help="Number of fact tables (default 40)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default 42)")
    args = parser.parse_args()

    summary = generate(args.output_dir, args.dims, args.facts, args.seed)
    print(f"Generated synthetic PBIP project at: {summary['output_dir']}")
    print(f"Tables: {summary['num_tables']} ({summary['num_dims']} dim + {summary['num_facts']} fact)")
    print(f"Relationships: {summary['num_relationships']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
