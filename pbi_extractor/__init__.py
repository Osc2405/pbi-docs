"""
pbi-docs - Power BI Documentation Generator

Tool to extract, clean and document Power BI data models (.pbit).
Generates human-readable documentation and context files for agents/LLMs.
"""

__version__ = "0.1.0"
__author__ = "Oscar Rosero"
__email__ = "orosero2405@gmail.com"

from .extractor import parse_datamodel_schema
from .processor import process_schema
from .formatters import clean_dax_expression, format_dax_expression
from .categorizer import is_technical_table, categorize_measure, get_column_category
from .documentation import generate_markdown, build_agent_context
from .diff import diff_models
from .jsonl_generator import generate_model_context, write_jsonl_context

__all__ = [
    "parse_datamodel_schema",
    "process_schema", 
    "clean_dax_expression",
    "format_dax_expression",
    "is_technical_table",
    "categorize_measure", 
    "get_column_category",
    "generate_markdown",
    "build_agent_context",
    "diff_models",
    "generate_model_context",
    "write_jsonl_context",
]
