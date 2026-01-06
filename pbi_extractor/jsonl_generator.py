"""
JSONL context generator for LLMs/agents.
Format optimized for embeddings and retrieval-augmented-generation.
"""

import json
from typing import Dict, List
from .formatters import format_dax_for_json, categorize_dax_complexity


def generate_table_context(table_data: dict) -> dict:
    """Generates JSONL context for a specific table."""
    visible_columns = [c for c in table_data["columns"] if not c["is_hidden"]]
    visible_measures = [m for m in table_data["measures"] if not m["is_hidden"]]
    
    # Generate column descriptions
    columns_info = []
    for col in visible_columns:
        columns_info.append({
            "name": col["name"],
            "type": col["data_type"],
            "desc": ""  # Placeholder for future descriptions
        })
    
    # Generate sample prompts based on measures
    sample_prompts = []
    if visible_measures:
        measure_names = [m["name"] for m in visible_measures[:3]]  # Top 3 measures
        for measure in measure_names:
            sample_prompts.append(f"What is the measure that calculates {measure.lower()}?")
            sample_prompts.append(f"Explain how the {measure} measure works")
    
    # Add prompts about relationships
    sample_prompts.extend([
        f"What relationships does the {table_data['name']} table have?",
        f"Explain the structure of the {table_data['name']} table"
    ])
    
    # Generate short summary
    measures_summary = ", ".join([m["name"] for m in visible_measures[:5]])
    short_summary = f"Table {table_data['name']}"
    if visible_columns:
        short_summary += f" with {len(visible_columns)} columns"
    if visible_measures:
        short_summary += f". Contains measures: {measures_summary}"
    
    return {
        "id": table_data["name"],
        "type": "table",
        "title": f"{table_data['name']} {'(Hidden)' if table_data['is_hidden'] else ''}",
        "columns": columns_info,
        "sample_prompts": sample_prompts[:6],  # Limitar a 6 prompts
        "short_summary": short_summary
    }


def generate_measure_context(measure_data: dict, table_name: str) -> dict:
    """Generates JSONL context for a specific measure."""
    expression = measure_data.get("expression", "")
    formatted_dax = format_dax_for_json(expression)
    complexity = categorize_dax_complexity(expression)
    
    # Generate sample prompts specific to this measure
    sample_prompts = [
        f"What does the {measure_data['name']} measure calculate?",
        f"Explain the formula for {measure_data['name']}",
        f"How to use {measure_data['name']} in an analysis?",
        f"What filters can I apply to {measure_data['name']}?"
    ]
    
    # Add specific prompts based on complexity
    if complexity == 'complex':
        sample_prompts.extend([
            f"Why is the {measure_data['name']} measure complex?",
            f"How to simplify {measure_data['name']}?"
        ])
    elif complexity == 'simple':
        sample_prompts.extend([
            f"How to optimize {measure_data['name']}?",
            f"What variations of {measure_data['name']} exist?"
        ])
    
    short_summary = f"Measure {measure_data['name']} of type {measure_data['category']}"
    if measure_data.get("format_string"):
        short_summary += f" with format {measure_data['format_string']}"
    
    return {
        "id": f"{table_name}.{measure_data['name']}",
        "type": "measure",
        "title": f"{measure_data['name']} ({measure_data['category']})",
        "expression": expression,
        "formatted_expression": formatted_dax,
        "format_string": measure_data.get("format_string", ""),
        "category": measure_data["category"],
        "complexity": complexity,
        "sample_prompts": sample_prompts,
        "short_summary": short_summary
    }


def generate_relationship_context(rel_data: dict) -> dict:
    """Generates JSONL context for a specific relationship."""
    sample_prompts = [
        f"How are {rel_data['from_table']} and {rel_data['to_table']} related?",
        f"Explain the cardinality between {rel_data['from_table']} and {rel_data['to_table']}",
        f"What does the {rel_data['name']} relationship mean?",
        f"How does filtering affect the relationship {rel_data['from_table']}.{rel_data['from_column']} -> {rel_data['to_table']}.{rel_data['to_column']}?"
    ]
    
    short_summary = f"Relationship {rel_data['cardinality']} between {rel_data['from_table']}.{rel_data['from_column']} and {rel_data['to_table']}.{rel_data['to_column']}"
    if not rel_data["is_active"]:
        short_summary += " (inactive)"
    
    return {
        "id": rel_data["name"],
        "type": "relationship",
        "title": f"Relationship: {rel_data['from_table']} -> {rel_data['to_table']}",
        "from_table": rel_data["from_table"],
        "from_column": rel_data["from_column"],
        "to_table": rel_data["to_table"],
        "to_column": rel_data["to_column"],
        "cardinality": rel_data["cardinality"],
        "cross_filtering": rel_data["cross_filtering"],
        "is_active": rel_data["is_active"],
        "sample_prompts": sample_prompts,
        "short_summary": short_summary
    }


def generate_model_context(cleaned_metadata: dict) -> List[dict]:
    """Generates complete model context in JSONL format."""
    context_entries = []
    
    # Add general model context
    model_context = {
        "id": "model_overview",
        "type": "model",
        "title": f"Model: {cleaned_metadata['file_name']}",
        "summary": cleaned_metadata["summary"],
        "compatibility_level": cleaned_metadata["compatibility_level"],
        "extraction_date": cleaned_metadata["extraction_date"],
        "sample_prompts": [
            "How many tables does this model have?",
            "What are the main measures in the model?",
            "Explain the general structure of the model",
            "What tables are related?"
        ],
        "short_summary": f"Power BI model with {cleaned_metadata['summary']['business_tables']} business tables, {cleaned_metadata['summary']['total_measures']} measures and {cleaned_metadata['summary']['total_relationships']} relationships"
    }
    context_entries.append(model_context)
    
    # Add table context
    business_tables = [t for t in cleaned_metadata["tables"] if not t["is_technical"]]
    for table in business_tables:
        if table["is_hidden"] and not any(not m["is_hidden"] for m in table.get("measures", [])):
            continue  # Skip hidden tables without visible measures
        
        table_context = generate_table_context(table)
        context_entries.append(table_context)
        
        # Add measure context for this table
        visible_measures = [m for m in table["measures"] if not m["is_hidden"]]
        for measure in visible_measures:
            measure_context = generate_measure_context(measure, table["name"])
            context_entries.append(measure_context)
    
    # Add relationship context
    for rel in cleaned_metadata["relationships"]:
        rel_context = generate_relationship_context(rel)
        context_entries.append(rel_context)
    
    return context_entries


def write_jsonl_context(context_entries: List[dict], output_path: str) -> None:
    """Writes the context in JSONL format."""
    with open(output_path, "w", encoding="utf-8") as f:
        for entry in context_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
