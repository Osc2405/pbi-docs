"""
CLI for Power BI metadata extractor.
Includes robust error handling and logging.
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Optional

from .extractor import parse_datamodel_schema, PBITExtractionError
from .pbip_extractor import parse_pbip_model, PBIPExtractionError, SemanticModelNotFoundError
from .processor import process_schema, ProcessingError
from .documentation import generate_markdown, build_agent_context
from .diff import diff_models, diff_impact
from .jsonl_generator import generate_model_context, write_jsonl_context
from .indexed_output import write_indexed_output
from . import resolver
from .resolver import ResolverError
from . import mcp_server
from . import graph_export


def detect_input_format(input_path: str) -> str:
    """Return 'pbit' or 'pbip' by inspecting the given path."""
    p = Path(input_path)
    if p.is_file():
        suffix = p.suffix.lower()
        if suffix == ".pbit":
            return "pbit"
        if suffix == ".pbip":
            return "pbip"
    if p.is_dir():
        if p.name.endswith(".SemanticModel"):
            return "pbip"
        if any(d.is_dir() and d.name.endswith(".SemanticModel") for d in p.iterdir()):
            return "pbip"
    raise ValueError(
        f"Cannot determine format for '{input_path}'. "
        "Supported: .pbit files, .pbip files, or a folder containing a .SemanticModel/ subfolder."
    )


def _get_model_name(input_path: Path, fmt: str) -> str:
    """Return a clean model name suitable for the output directory."""
    if fmt == "pbit":
        return f"{input_path.stem}.pbit"   # preserves existing behaviour
    name = input_path.name
    if name.endswith(".SemanticModel"):
        return name[: -len(".SemanticModel")]
    if input_path.suffix.lower() == ".pbip":
        return input_path.stem
    # Project root folder: use the .SemanticModel subfolder name
    for d in input_path.iterdir():
        if d.is_dir() and d.name.endswith(".SemanticModel"):
            return d.name[: -len(".SemanticModel")]
    return input_path.stem


# Configure logging
def setup_logging(verbose: bool = False) -> None:
    """Configure the logging system."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


# Constants
DEFAULT_OUTPUT_BASE = Path("output")


def process_file(input_file: Path, output_base: Path, lang: str = "en",
                 index_format: str = "json", pretty: bool = False) -> dict:
    """Process a .pbit or .pbip model and generate all metadata.

    Args:
        input_file: Path to the .pbit file, .pbip file, or PBIP folder
        output_base: Base output directory
        lang: Language code for documentation ('en' or 'es')
        index_format: Output format for indexed output ('json', 'toon', or 'auto')
        pretty: If True, indent the indexed output JSON files for human
                debugging. Default False (compact — see indexed_output.py).

    Returns:
        dict: Processed metadata

    Raises:
        PBITExtractionError: If there are extraction errors (.pbit)
        PBIPExtractionError: If there are extraction errors (.pbip / TMDL)
        ProcessingError: If there are processing errors
    """
    logger = logging.getLogger(__name__)

    try:
        logger.info(f"Processing: {input_file}")

        fmt = detect_input_format(str(input_file))
        model_name = _get_model_name(input_file, fmt)
        output_dir = output_base / model_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Extract schema
        if fmt == "pbit":
            logger.debug("Extracting schema from .pbit file")
            schema = parse_datamodel_schema(str(input_file))
        else:
            logger.debug("Extracting schema from PBIP / TMDL")
            schema = parse_pbip_model(str(input_file))

        logger.info(f"Schema extracted successfully: {len(schema.get('model', {}).get('tables', []))} tables")

        # Process schema
        logger.debug("Processing schema and generating metadata")
        metadata = process_schema(schema, str(input_file))
        logger.info(f"Metadata processed: {metadata['summary']['total_tables']} tables, {metadata['summary']['total_measures']} measures")
        
        # Save metadata JSON
        metadata_path = output_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.info(f"Metadata saved to: {metadata_path}")
        
        # Generate Markdown documentation (with language)
        logger.debug(f"Generating Markdown documentation in {lang}")
        markdown_content = generate_markdown(metadata, lang=lang)
        markdown_path = output_dir / "model_documentation.md"
        with open(markdown_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        logger.info(f"Documentation saved to: {markdown_path}")
        
        # agent_context.json/model_context.jsonl are backwards-compat outputs for
        # external consumers (e.g. existing RAG pipelines) — neither is read by
        # resolver.py/mcp_server.py, so skipping them would save generation
        # time/disk, not query-time tokens. Left always-on; see CHANGELOG for
        # the decision record.
        # Generate agent context (JSON) (with language)
        logger.debug("Generating agent context")
        agent_context = build_agent_context(metadata, lang=lang)
        agent_path = output_dir / "agent_context.json"
        with open(agent_path, "w", encoding="utf-8") as f:
            json.dump(agent_context, f, indent=2, ensure_ascii=False)
        logger.info(f"Agent context saved to: {agent_path}")
        
        # Generate JSONL context for LLMs
        logger.debug("Generating JSONL context for LLMs")
        jsonl_context = generate_model_context(metadata)
        jsonl_path = output_dir / "model_context.jsonl"
        write_jsonl_context(jsonl_context, jsonl_path)
        logger.info(f"JSONL context saved to: {jsonl_path}")

        # Generate indexed output (index.json, tables/*.json, relationships.json)
        logger.debug(f"Generating indexed output (format: {index_format})")
        write_indexed_output(metadata, output_dir,
                             source_format=fmt, index_format=index_format, pretty=pretty)
        logger.info(f"Indexed output written to: {output_dir}")

        logger.info(f"Processing completed successfully for: {input_file.name}")
        return metadata
        
    except (PBITExtractionError, PBIPExtractionError) as e:
        logger.error(f"Extraction error in {input_file}: {e}")
        raise
    except ProcessingError as e:
        logger.error(f"Processing error in {input_file}: {e}")
        raise
    except ValueError as e:
        logger.error(f"Format detection error for {input_file}: {e}")
        raise PBITExtractionError(str(e))
    except Exception as e:
        logger.error(f"Unexpected error processing {input_file}: {e}")
        raise PBITExtractionError(f"Unexpected error: {e}")


def _run_query(args) -> int:
    """Handle --query mode: dispatch to resolver.py and print JSON to stdout."""
    logger = logging.getLogger(__name__)
    try:
        if args.list_tables:
            result = resolver.list_tables(
                args.query,
                hidden=True if args.hidden else None,
                technical=True if args.technical else None,
                category=args.category,
            )
        elif args.relationships:
            result = resolver.get_relationships(args.query, table=args.table)
        elif args.table and args.measure and args.dependencies:
            result = resolver.get_measure_dependencies(args.query, args.table, args.measure,
                                                        transitive=args.transitive)
        elif args.table and args.measure and args.usages:
            result = resolver.find_measure_usages(args.query, args.table, args.measure,
                                                   transitive=args.transitive)
        elif args.table and args.measure:
            result = resolver.get_measure(args.query, args.table, args.measure)
        elif args.table:
            result = resolver.get_table(args.query, args.table)
        elif args.search_measures is not None:
            result = resolver.search_measures(args.query, args.search_measures, category=args.category)
        elif args.search_columns:
            result = resolver.search_columns(args.query, args.search_columns, category=args.category)
        elif args.export_graph:
            graph = graph_export.build_graph(args.query)
            if args.export_graph == "graphml":
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
                print(graph_export.to_graphml(graph))
                return 0
            result = graph
        else:
            logger.error("--query requires one of: --list-tables, --table, --search-measures, "
                        "--search-columns, --relationships, --dependencies, --usages, "
                        "--export-graph")
            return 1

        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except ResolverError as e:
        logger.error(str(e))
        return 1


def main(argv: Optional[list] = None) -> int:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Power BI metadata extractor (.pbit / .pbip)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s -i file.pbit                         # Process a .pbit file
  %(prog)s -i my-model.SemanticModel            # Process a PBIP SemanticModel folder
  %(prog)s -i project/                          # Process a PBIP project folder
  %(prog)s -i file.pbit -o output              # Change output directory
  %(prog)s --batch "data/**/*.pbit"            # Batch process .pbit files
  %(prog)s --diff old.pbit new.pbip            # Compare two models (mixed formats ok)
  %(prog)s -i file.pbit --lang es              # Spanish documentation
  %(prog)s -i model.SemanticModel --index-format json  # Indexed output (default)
  %(prog)s --query output/my-model --list-tables       # Query an already-processed model
  %(prog)s --query output/my-model --table "Sales"
  %(prog)s --query output/my-model --table "Sales" --measure "Total Sales"
  %(prog)s --query output/my-model --search-measures "revenue"
  %(prog)s --query output/my-model --search-columns "customer"
  %(prog)s --query output/my-model --relationships --table "Sales"
  %(prog)s --query output/my-model --table "Sales" --measure "Margin %%" --dependencies
  %(prog)s --query output/my-model --table "Sales" --measure "Sales Amount" --usages
  %(prog)s --query output/my-model --export-graph              # Node/edge JSON graph
  %(prog)s --query output/my-model --export-graph graphml > model.graphml
  %(prog)s --mcp-serve output/my-model                # Run a read-only MCP server (stdio)
        """
    )

    parser.add_argument(
        "--input", "-i",
        type=Path,
        help="Path to a .pbit file, .pbip file, .SemanticModel/ folder, or project root folder"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT_BASE,
        help=f"Base output directory (default: {DEFAULT_OUTPUT_BASE})"
    )
    parser.add_argument(
        "--batch",
        type=str,
        help="Glob pattern to process multiple files/folders (e.g., 'data/*.pbit')"
    )
    parser.add_argument(
        "--diff",
        nargs=2,
        metavar=("A", "B"),
        type=Path,
        help="Compare two models and generate diff (mixed .pbit/.pbip supported)"
    )
    parser.add_argument(
        "--diff-impact",
        action="store_true",
        dest="diff_impact",
        help="Combine with --diff: also report which measures depend on each "
             "removed/modified measure (impact analysis). Combine with --transitive "
             "to follow the dependency chain beyond one level."
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose mode (more debugging information)"
    )
    parser.add_argument(
        "--lang", "--language",
        type=str,
        default="en",
        choices=["en", "es"],
        help="Language for documentation: 'en' (English) or 'es' (Spanish). Default: 'en'"
    )
    parser.add_argument(
        "--index-format",
        type=str,
        default="json",
        choices=["json", "toon", "auto"],
        dest="index_format",
        help="Format for indexed output files: 'json', 'toon', or 'auto' "
             "(per-table: TOON for large/uniform tables, JSON for small ones). Default: json"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Indent indexed output JSON (index.json, tables/*.json, relationships.json) "
             "for human debugging. Default: compact (these files are meant for "
             "resolver.py/mcp_server.py/LLM consumption, not human reading)."
    )
    parser.add_argument(
        "--query",
        type=Path,
        metavar="MODEL_DIR",
        help="Query an already-processed model's output directory (e.g. output/my-model) "
             "instead of extracting. Combine with --list-tables, --table, --search-measures, "
             "or --relationships."
    )
    parser.add_argument("--list-tables", action="store_true", help="Query mode: list tables")
    parser.add_argument("--table", type=str, metavar="NAME", help="Query mode: get one table's detail")
    parser.add_argument("--measure", type=str, metavar="NAME",
                        help="Query mode: combine with --table to get one measure's full record")
    parser.add_argument("--search-measures", type=str, metavar="QUERY",
                        dest="search_measures", help="Query mode: find measures by name substring")
    parser.add_argument("--search-columns", type=str, metavar="QUERY",
                        dest="search_columns", help="Query mode: find columns by name substring")
    parser.add_argument("--relationships", action="store_true", help="Query mode: list relationships")
    parser.add_argument("--export-graph", nargs="?", const="json", choices=["json", "graphml"],
                        dest="export_graph", metavar="FORMAT",
                        help="Query mode: project the model's tables/relationships to a graph "
                             "(json node/edge lists, or graphml XML for Gephi/yEd). Default: json.")
    parser.add_argument("--dependencies", action="store_true",
                        help="Query mode: combine with --table/--measure to list what it references")
    parser.add_argument("--usages", action="store_true",
                        help="Query mode: combine with --table/--measure to find what references it "
                             "(impact analysis)")
    parser.add_argument("--transitive", action="store_true",
                        help="Query mode: combine with --dependencies/--usages to follow the chain "
                             "(default: one level deep only)")
    parser.add_argument("--hidden", action="store_true", help="Query mode: filter --list-tables to hidden tables")
    parser.add_argument("--technical", action="store_true", help="Query mode: filter --list-tables to technical tables")
    parser.add_argument("--category", type=str, metavar="NAME",
                        help="Query mode: filter --list-tables/--search-measures by measure category")
    parser.add_argument(
        "--mcp-serve",
        type=Path,
        metavar="MODEL_DIR",
        dest="mcp_serve",
        help="Run a read-only MCP server (stdio) bound to an already-processed model's output "
             "directory (e.g. output/my-model). Blocks reading JSON-RPC from stdin until EOF."
    )

    args = parser.parse_args(argv)

    # Configure logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    # ── query mode ────────────────────────────────────────────────────────
    if args.query:
        return _run_query(args)

    # ── MCP server mode ──────────────────────────────────────────────────
    if args.mcp_serve:
        mcp_server.run(args.mcp_serve)
        return 0

    try:
        args.output.mkdir(parents=True, exist_ok=True)

        # ── diff mode ──────────────────────────────────────────────────────
        if args.diff:
            a_path, b_path = args.diff
            logger.info(f"Comparing models: {a_path.name} vs {b_path.name}")
            try:
                name_a = _get_model_name(a_path, detect_input_format(str(a_path)))
                name_b = _get_model_name(b_path, detect_input_format(str(b_path)))
                # Two different model paths commonly share the same basename —
                # e.g. the same project compared at two commits/checkouts, the
                # single most common real-world diff scenario. process_file()
                # writes to output_base/model_name, so a naive second call
                # would silently overwrite the first model's output *before*
                # diff_impact() reads model_dir_a back from disk, making every
                # "used_by" empty regardless of real dependencies (see
                # CHANGELOG). Route b into a separate subdirectory whenever
                # names collide; otherwise keep the existing flat layout.
                output_base_b = args.output / "_diff_b" if name_a == name_b else args.output

                meta_a = process_file(a_path, args.output, lang=args.lang,
                                      index_format=args.index_format, pretty=args.pretty)
                meta_b = process_file(b_path, output_base_b, lang=args.lang,
                                      index_format=args.index_format, pretty=args.pretty)
                diff = diff_models(meta_a, meta_b)
                if args.diff_impact:
                    model_dir_a = args.output / name_a
                    model_dir_b = output_base_b / name_b
                    diff.update(diff_impact(diff, model_dir_a, model_dir_b, transitive=args.transitive))
                diff_name = f"diff_{a_path.stem}_vs_{b_path.stem}.json"
                diff_path = args.output / diff_name
                with open(diff_path, "w", encoding="utf-8") as f:
                    json.dump(diff, f, indent=2, ensure_ascii=False)
                logger.info(f"Diff saved to: {diff_path}")
                logger.info(
                    "Summary: "
                    f"measures +{len(diff['measures_added'])}/"
                    f"-{len(diff['measures_removed'])}/"
                    f"~{len(diff['measures_modified'])}, "
                    f"columns +{len(diff['columns_added'])}/"
                    f"-{len(diff['columns_removed'])}/"
                    f"~{len(diff['columns_modified'])}, "
                    f"relationships +{len(diff['relationships_added'])}/"
                    f"-{len(diff['relationships_removed'])}/"
                    f"~{len(diff['relationships_modified'])}"
                )
                return 0
            except Exception as e:
                logger.error(f"Error in comparison: {e}")
                return 1

        # ── batch mode ─────────────────────────────────────────────────────
        if args.batch:
            import glob
            matched = glob.glob(args.batch)
            if not matched:
                logger.warning(f"No files found for pattern: {args.batch}")
                return 1
            logger.info(f"Processing {len(matched)} items in batch mode")
            success_count = 0
            for path_str in matched:
                try:
                    process_file(Path(path_str), args.output, lang=args.lang,
                                 index_format=args.index_format, pretty=args.pretty)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing {path_str}: {e}")
            logger.info(f"Batch completed: {success_count}/{len(matched)} successful")
            return 0 if success_count == len(matched) else 1

        # ── single input ───────────────────────────────────────────────────
        if not args.input:
            logger.error("Must provide --input, --batch, or --diff")
            parser.print_help()
            return 1

        if not args.input.exists():
            logger.error(f"Path does not exist: {args.input}")
            return 1

        try:
            detect_input_format(str(args.input))
        except ValueError as e:
            logger.error(str(e))
            return 1

        process_file(args.input, args.output, lang=args.lang,
                     index_format=args.index_format, pretty=args.pretty)
        return 0

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())