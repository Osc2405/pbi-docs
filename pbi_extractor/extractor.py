"""
Extraction of DataModelSchema from .pbit files.
Includes robust validations and explicit error handling.
"""

import json
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional


class PBITExtractionError(Exception):
    """Base exception for .pbit extraction errors"""
    pass


class FileNotFoundError(PBITExtractionError):
    """File not found or not a valid .pbit file"""
    pass


class SchemaNotFoundError(PBITExtractionError):
    """Model schema not found in file"""
    pass


class SchemaParseError(PBITExtractionError):
    """Error parsing the JSON schema"""
    pass


def validate_input_file(input_file: str) -> Path:
    """Validates that the input file is valid."""
    file_path = Path(input_file)
    
    if not file_path.exists():
        raise FileNotFoundError(f"File does not exist: {input_file}")
    
    if not file_path.is_file():
        raise FileNotFoundError(f"Path is not a file: {input_file}")
    
    if file_path.suffix.lower() not in ['.pbit']:
        raise FileNotFoundError(f"Only .pbit files are supported, received: {file_path.suffix}")
    
    if file_path.stat().st_size == 0:
        raise FileNotFoundError(f"File is empty: {input_file}")
    
    return file_path


def validate_zip_structure(zip_ref: zipfile.ZipFile) -> List[str]:
    """Validates the ZIP file structure and returns relevant files."""
    files = zip_ref.namelist()
    
    if not files:
        raise SchemaNotFoundError("The .pbit file is empty or corrupted")
    
    # Search for model files
    model_files = [f for f in files if any(key in f for key in ["DataModelSchema", "DataModel", "model.json"])]
    
    if not model_files:
        available_files = [f for f in files if not f.startswith('_')][:10]  # First 10 non-hidden files
        raise SchemaNotFoundError(
            f"DataModelSchema, DataModel or model.json not found in file. "
            f"Available files: {', '.join(available_files)}"
        )
    
    return model_files


def clean_json_text(text: str) -> str:
    """Cleans JSON text by removing comments and trailing commas."""
    # Remove BOM and NULLs
    cleaned = text.lstrip("\ufeff").replace("\x00", "")
    
    # Remove // line comments
    cleaned = re.sub(r"(^|[\s{,\[])[ \t]*//.*?$", r"\\1", cleaned, flags=re.MULTILINE)
    
    # Remove /* */ block comments
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)
    
    # Remove trailing commas before } or ]
    cleaned = re.sub(r",\s*([}\]])", r"\\1", cleaned)
    
    return cleaned


def parse_json_with_fallback(raw_bytes: bytes, filename: str) -> dict:
    """Attempts to parse JSON with multiple encodings and cleaning."""
    encodings = ["utf-8", "utf-16", "latin-1"]
    
    for encoding in encodings:
        try:
            schema_text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise SchemaParseError(f"Could not decode file {filename} with any encoding")
    
    # Try to parse directly
    try:
        return json.loads(schema_text)
    except json.JSONDecodeError as e:
        # Try with cleaning
        try:
            cleaned_text = clean_json_text(schema_text)
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e2:
            # Save snippet for debugging
            snippet = cleaned_text[:500] if len(cleaned_text) > 500 else cleaned_text
            raise SchemaParseError(
                f"Error parsing JSON in {filename}. "
                f"Original error: {str(e)}. "
                f"Error after cleaning: {str(e2)}. "
                f"Snippet: {snippet}"
            )


def validate_schema_structure(schema: dict) -> None:
    """Validates that the schema has the expected structure."""
    if not isinstance(schema, dict):
        raise SchemaParseError("Schema must be a JSON object")
    
    if "model" not in schema:
        available_keys = list(schema.keys())[:5]  # First 5 keys
        raise SchemaParseError(
            f"Schema does not contain 'model' key. "
            f"Available keys: {', '.join(available_keys)}"
        )
    
    model = schema["model"]
    if not isinstance(model, dict):
        raise SchemaParseError("The 'model' key must be an object")
    
    # Validate minimum model structure
    required_keys = ["tables", "relationships"]
    missing_keys = [key for key in required_keys if key not in model]
    if missing_keys:
        raise SchemaParseError(f"Model does not contain required keys: {', '.join(missing_keys)}")
    
    if not isinstance(model["tables"], list):
        raise SchemaParseError("The 'tables' key must be a list")
    
    if not isinstance(model["relationships"], list):
        raise SchemaParseError("The 'relationships' key must be a list")


def parse_datamodel_schema(input_file: str) -> dict:
    """Reads and parses the DataModelSchema from a .pbit file.
    
    Args:
        input_file: Path to the .pbit file
        
    Returns:
        dict: Parsed model schema
        
    Raises:
        FileNotFoundError: If the file does not exist or is not valid
        SchemaNotFoundError: If the model schema is not found
        SchemaParseError: If there are errors parsing the JSON
    """
    # Validate input file
    file_path = validate_input_file(input_file)
    
    try:
        with zipfile.ZipFile(file_path, "r") as zip_ref:
            # Validate ZIP structure
            model_files = validate_zip_structure(zip_ref)
            
            # Try to parse each found model file
            last_error = None
            for model_file in model_files:
                try:
                    raw_bytes = zip_ref.read(model_file)
                    schema = parse_json_with_fallback(raw_bytes, model_file)
                    validate_schema_structure(schema)
                    return schema
                except Exception as e:
                    last_error = e
                    continue
            
            # If we get here, no file could be parsed
            raise SchemaParseError(
                f"Could not parse any model file. "
                f"Files attempted: {', '.join(model_files)}. "
                f"Last error: {str(last_error)}"
            )
            
    except zipfile.BadZipFile:
        raise FileNotFoundError(f"File is not a valid ZIP: {input_file}")
    except Exception as e:
        if isinstance(e, PBITExtractionError):
            raise
        raise PBITExtractionError(f"Unexpected error processing {input_file}: {str(e)}")