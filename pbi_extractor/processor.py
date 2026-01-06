"""
Model processing: counts, columns, measures, relationships and summaries.
Includes robust validations and error handling.
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from .extractor import PBITExtractionError


class ProcessingError(PBITExtractionError):
    """Error during schema processing"""
    pass


def validate_table_structure(table: dict, table_name: str) -> None:
    """Validates the structure of a table."""
    if not isinstance(table, dict):
        raise ProcessingError(f"Table '{table_name}' must be an object")
    
    required_keys = ["name"]
    missing_keys = [key for key in required_keys if key not in table]
    if missing_keys:
        raise ProcessingError(f"Table '{table_name}' does not contain required keys: {', '.join(missing_keys)}")
    
    if not isinstance(table.get("columns", []), list):
        raise ProcessingError(f"Columns of table '{table_name}' must be a list")
    
    if not isinstance(table.get("measures", []), list):
        raise ProcessingError(f"Measures of table '{table_name}' must be a list")


def validate_column_structure(col: dict, col_index: int, table_name: str) -> None:
    """Validates the structure of a column."""
    if not isinstance(col, dict):
        raise ProcessingError(f"Column {col_index} of table '{table_name}' must be an object")
    
    required_keys = ["name"]
    missing_keys = [key for key in required_keys if key not in col]
    if missing_keys:
        raise ProcessingError(f"Column {col_index} of table '{table_name}' does not contain: {', '.join(missing_keys)}")


def validate_measure_structure(measure: dict, measure_index: int, table_name: str) -> None:
    """Validates the structure of a measure."""
    if not isinstance(measure, dict):
        raise ProcessingError(f"Measure {measure_index} of table '{table_name}' must be an object")
    
    required_keys = ["name"]
    missing_keys = [key for key in required_keys if key not in measure]
    if missing_keys:
        raise ProcessingError(f"Measure {measure_index} of table '{table_name}' does not contain: {', '.join(missing_keys)}")


def validate_relationship_structure(rel: dict, rel_index: int) -> None:
    """Validates the structure of a relationship."""
    if not isinstance(rel, dict):
        raise ProcessingError(f"Relationship {rel_index} must be an object")
    
    required_keys = ["fromTable", "fromColumn", "toTable", "toColumn"]
    missing_keys = [key for key in required_keys if key not in rel]
    if missing_keys:
        raise ProcessingError(f"Relationship {rel_index} does not contain required keys: {', '.join(missing_keys)}")


def safe_get_column_category(data_type: str, name: str) -> str:
    """Gets the category of a column safely."""
    try:
        from .categorizer import get_column_category
        return get_column_category(data_type, name)
    except Exception as e:
        print(f"Warning: Error categorizing column '{name}': {e}")
        return "other"


def safe_categorize_measure(name: str, expression: str) -> str:
    """Categorizes a measure safely."""
    try:
        from .categorizer import categorize_measure
        return categorize_measure(name, expression)
    except Exception as e:
        print(f"Warning: Error categorizing measure '{name}': {e}")
        return "other"


def safe_clean_dax(expression: str, measure_name: str) -> str:
    """Cleans a DAX expression safely."""
    try:
        from .formatters import clean_dax_expression
        return clean_dax_expression(expression)
    except Exception as e:
        print(f"Warning: Error cleaning DAX for measure '{measure_name}': {e}")
        return expression


def safe_format_dax(expression: str, measure_name: str) -> str:
    """Formats a DAX expression safely."""
    try:
        from .formatters import format_dax_expression
        return format_dax_expression(expression)
    except Exception as e:
        print(f"Warning: Error formatting DAX for measure '{measure_name}': {e}")
        return expression


from .categorizer import is_technical_table
from .formatters import clean_dax_expression, format_dax_expression


def process_schema(schema: dict, input_file: str) -> dict:
    """Transforms raw schema to cleaned_metadata with counts and structure.
    
    Args:
        schema: Parsed model schema
        input_file: Path to input file
        
    Returns:
        dict: Processed and validated metadata
        
    Raises:
        ProcessingError: If there are errors in the schema structure
    """
    try:
        model = schema["model"]
    except KeyError:
        raise ProcessingError("Schema does not contain 'model' key")
    
    if not isinstance(model, dict):
        raise ProcessingError("The 'model' key must be an object")
    
    # Validate basic structure
    required_keys = ["tables", "relationships"]
    missing_keys = [key for key in required_keys if key not in model]
    if missing_keys:
        raise ProcessingError(f"Model does not contain required keys: {', '.join(missing_keys)}")
    
    tables = model.get("tables", [])
    relationships = model.get("relationships", [])
    
    if not isinstance(tables, list):
        raise ProcessingError("Tables must be a list")
    
    if not isinstance(relationships, list):
        raise ProcessingError("Relationships must be a list")
    
    cleaned_metadata = {
        "file_name": Path(input_file).stem,
        "extraction_date": datetime.now().isoformat(),
        "compatibility_level": schema.get("compatibilityLevel", "unknown"),
        "summary": {
            "total_tables": len(tables),
            "business_tables": 0,
            "technical_tables": 0,
            "total_columns": 0,
            "total_measures": 0,
            "total_relationships": len(relationships),
        },
        "tables": [],
        "relationships": [],
    }

    # Procesar tablas con validación
    for table in tables:
        try:
            table_name = table.get("name", "Unknown")
            validate_table_structure(table, table_name)
            
            is_hidden = table.get("isHidden", False)
            is_technical = is_technical_table(table_name)

            columns = table.get("columns", [])
            measures = table.get("measures", [])

            processed_columns: List[Dict] = []
            for i, col in enumerate(columns):
                try:
                    validate_column_structure(col, i, table_name)
                    
                    col_data = {
                        "name": col.get("name", ""),
                        "data_type": col.get("dataType", "unknown"),
                        "is_hidden": col.get("isHidden", False),
                        "source_column": col.get("sourceColumn", ""),
                        "format_string": col.get("formatString", ""),
                        "category": safe_get_column_category(col.get("dataType", "unknown"), col.get("name", "")),
                    }
                    processed_columns.append(col_data)
                    if not col_data["is_hidden"]:
                        cleaned_metadata["summary"]["total_columns"] += 1
                        
                except Exception as e:
                    print(f"Warning: Error processing column {i} in table '{table_name}': {e}")
                    continue

            processed_measures: List[Dict] = []
            for i, measure in enumerate(measures):
                try:
                    validate_measure_structure(measure, i, table_name)
                    
                    raw_expression = measure.get("expression", "")
                    cleaned_expression = safe_clean_dax(raw_expression, measure.get("name", ""))
                    formatted_expression = safe_format_dax(cleaned_expression, measure.get("name", ""))
                    
                    measure_data = {
                        "name": measure.get("name", ""),
                        "expression": cleaned_expression,
                        "formatted_expression": formatted_expression,
                        "format_string": measure.get("formatString", ""),
                        "is_hidden": measure.get("isHidden", False),
                        "display_folder": measure.get("displayFolder", ""),
                        "category": safe_categorize_measure(measure.get("name", ""), cleaned_expression),
                    }
                    processed_measures.append(measure_data)
                    if not measure_data["is_hidden"]:
                        cleaned_metadata["summary"]["total_measures"] += 1
                        
                except Exception as e:
                    print(f"Warning: Error processing measure {i} in table '{table_name}': {e}")
                    continue

            table_data = {
                "name": table_name,
                "is_hidden": is_hidden,
                "is_technical": is_technical,
                "columns": processed_columns,
                "measures": processed_measures,
                "partition_count": len(table.get("partitions", [])),
            }
            cleaned_metadata["tables"].append(table_data)
            if is_technical:
                cleaned_metadata["summary"]["technical_tables"] += 1
            else:
                cleaned_metadata["summary"]["business_tables"] += 1
                
        except Exception as e:
            print(f"Warning: Error processing table '{table.get('name', 'unknown')}': {e}")
            continue

    # Procesar relaciones con validación
    for i, rel in enumerate(relationships):
        try:
            validate_relationship_structure(rel, i)
            
            rel_data = {
                "name": rel.get("name", ""),
                "from_table": rel.get("fromTable", ""),
                "from_column": rel.get("fromColumn", ""),
                "to_table": rel.get("toTable", ""),
                "to_column": rel.get("toColumn", ""),
                "cardinality": f"{rel.get('fromCardinality', 'many')}:{rel.get('toCardinality', 'one')}",
                "cross_filtering": rel.get("crossFilteringBehavior", "OneDirection"),
                "is_active": rel.get("isActive", True),
            }
            cleaned_metadata["relationships"].append(rel_data)
            
        except Exception as e:
            print(f"Warning: Error processing relationship {i}: {e}")
            continue

    return cleaned_metadata
