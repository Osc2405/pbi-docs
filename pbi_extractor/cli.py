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
from .processor import process_schema, ProcessingError
from .documentation import generate_markdown, build_agent_context
from .diff import diff_models
from .jsonl_generator import generate_model_context, write_jsonl_context


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


def process_file(input_file: Path, output_base: Path, lang: str = "en") -> dict:
    """Process a .pbit file and generate all metadata.
    
    Args:
        input_file: .pbit file to process
        output_base: Base output directory
        lang: Language code for documentation ('en' or 'es')
        
    Returns:
        dict: Processed metadata
        
    Raises:
        PBITExtractionError: If there are extraction errors
        ProcessingError: If there are processing errors
    """
    logger = logging.getLogger(__name__)
    
    try:
        logger.info(f"Processing file: {input_file}")
        
        # Create output directory specific to this file
        output_dir = output_base / f"{input_file.stem}.pbit"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract schema
        logger.debug("Extracting schema from .pbit file")
        schema = parse_datamodel_schema(str(input_file))
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
        
        logger.info(f"Processing completed successfully for: {input_file.name}")
        return metadata
        
    except PBITExtractionError as e:
        logger.error(f"Extraction error in {input_file}: {e}")
        raise
    except ProcessingError as e:
        logger.error(f"Processing error in {input_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error processing {input_file}: {e}")
        raise PBITExtractionError(f"Unexpected error: {e}")


def main(argv: Optional[list] = None) -> int:
    """Main CLI function."""
    parser = argparse.ArgumentParser(
        description="Power BI metadata extractor (.pbit)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Usage examples:
  %(prog)s -i file.pbit                       # Process a file
  %(prog)s -i file.pbit -o output            # Change output directory
  %(prog)s --batch "data/pbit/*.pbit"        # Process multiple files
  %(prog)s --diff old.pbit new.pbit          # Compare two models
  %(prog)s -v -i file.pbit                   # Verbose mode
  %(prog)s -i file.pbit --lang es            # Generate Spanish documentation
        """
    )
    
    parser.add_argument(
        "--input", "-i", 
        type=Path, 
        help="Path to .pbit file"
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
        help="Glob pattern to process multiple files (e.g., data/pbit/*.pbit)"
    )
    parser.add_argument(
        "--diff", 
        nargs=2, 
        metavar=("A", "B"), 
        type=Path, 
        help="Compare two .pbit files and generate diff"
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
    
    args = parser.parse_args(argv)
    
    # Validate language
    if args.lang not in ["en", "es"]:
        print(f"Error: Invalid language '{args.lang}'. Must be 'en' or 'es'.", file=sys.stderr)
        return 1
    
    # Configure logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    try:
        # Create output directory if it doesn't exist
        args.output.mkdir(parents=True, exist_ok=True)
        
        # Process diff mode
        if args.diff:
            a_path, b_path = args.diff
            logger.info(f"Comparing models: {a_path.name} vs {b_path.name}")
            
            try:
                meta_a = process_file(a_path, args.output, lang=args.lang)
                meta_b = process_file(b_path, args.output, lang=args.lang)
                
                logger.debug("Generating diff between models")
                diff = diff_models(meta_a, meta_b)
                
                diff_name = f"diff_{a_path.stem}_vs_{b_path.stem}.json"
                diff_path = args.output / diff_name
                
                with open(diff_path, "w", encoding="utf-8") as f:
                    json.dump(diff, f, indent=2, ensure_ascii=False)
                
                logger.info(f"Diff saved to: {diff_path}")
                return 0
                
            except Exception as e:
                logger.error(f"Error in comparison: {e}")
                return 1
        
        # Process batch mode
        if args.batch:
            import glob
            matched = glob.glob(args.batch)
            
            if not matched:
                logger.warning(f"No files found for pattern: {args.batch}")
                return 1
            
            logger.info(f"Processing {len(matched)} files in batch mode")
            success_count = 0
            
            for path_str in matched:
                try:
                    process_file(Path(path_str), args.output, lang=args.lang)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Error processing {path_str}: {e}")
                    continue
            
            logger.info(f"Batch processing completed: {success_count}/{len(matched)} files successful")
            return 0 if success_count == len(matched) else 1
        
        # Process individual file
        if not args.input:
            logger.error("Must provide --input or use --batch/--diff")
            parser.print_help()
            return 1
        
        if not args.input.exists():
            logger.error(f"File does not exist: {args.input}")
            return 1
        
        if not args.input.suffix.lower() == '.pbit':
            logger.error(f"Only .pbit files are supported, received: {args.input.suffix}")
            return 1
        
        process_file(args.input, args.output, lang=args.lang)
        return 0
        
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())