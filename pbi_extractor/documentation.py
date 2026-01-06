"""
Generation of Markdown documentation and agent_context.json from cleaned_metadata.
Includes advanced DAX formatting for better readability.
"""

from datetime import datetime
from typing import Dict, List

from .formatters import format_dax_for_documentation, format_dax_for_json, categorize_dax_complexity
from .i18n import get_translation, get_category_name, get_complexity_label


def generate_markdown(cleaned_metadata: dict, lang: str = "en") -> str:
    summary = cleaned_metadata["summary"]
    business_tables = [t for t in cleaned_metadata["tables"] if not t["is_technical"]]

    doc = f"# {cleaned_metadata['file_name']} - {get_translation(lang, 'power_bi_data_model')}\n\n"
    doc += f"**{get_translation(lang, 'generated')}:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    doc += f"## {get_translation(lang, 'model_summary')}\n\n"
    doc += f"- **{get_translation(lang, 'business_tables')}:** {summary['business_tables']}\n"
    doc += f"- **{get_translation(lang, 'total_columns')}:** {summary['total_columns']}\n"
    doc += f"- **{get_translation(lang, 'total_measures')}:** {summary['total_measures']}\n"
    doc += f"- **{get_translation(lang, 'relationships')}:** {summary['total_relationships']}\n\n"
    doc += "---\n\n"
    doc += f"## {get_translation(lang, 'tables_and_measures')}\n\n"

    for table in business_tables:
        if table["is_hidden"] and not any(not m["is_hidden"] for m in table.get("measures", [])):
            continue
        if table["is_hidden"]:
            doc += f"### {table['name']} *({get_translation(lang, 'hidden_table_measures_only')})*\n\n"
        else:
            doc += f"### {table['name']}\n\n"

        visible_columns = [c for c in table["columns"] if not c["is_hidden"]]
        if visible_columns:
            doc += f"**{get_translation(lang, 'columns')}:**\n\n"
            doc += f"| {get_translation(lang, 'column')} | {get_translation(lang, 'type')} | {get_translation(lang, 'category')} |\n"
            doc += "|--------|------|----------|\n"
            for col in visible_columns:
                doc += f"| `{col['name']}` | {col['data_type']} | {col['category']} |\n"
            doc += "\n"

        visible_measures = [m for m in table["measures"] if not m["is_hidden"]]
        if visible_measures:
            doc += f"**{get_translation(lang, 'measures')}:**\n\n"
            measures_by_category: Dict[str, List[dict]] = {}
            for measure in visible_measures:
                measures_by_category.setdefault(measure.get("category", "other"), []).append(measure)

            category_order = [
                "revenue",
                "cost",
                "margin",
                "percentage",
                "ratio",
                "temporal",
                "calendar_intelligence",
                "aggregation",
                "filtering",
                "other",
            ]
            for category in category_order:
                if category in measures_by_category:
                    doc += f"##### {get_category_name(lang, category)}\n\n"
                    for measure in measures_by_category[category]:
                        # Obtener expresión DAX y formatearla
                        expression = measure.get("expression", "")
                        formatted_dax = format_dax_for_documentation(expression)
                        complexity = categorize_dax_complexity(expression)
                        
                        doc += f"**{measure['name']}**"
                        
                        # Añadir indicador de complejidad
                        complexity_label = get_complexity_label(lang, complexity)
                        doc += f" *({complexity_label})*\n\n"
                        
                        if measure.get("display_folder"):
                            doc += f"*{get_translation(lang, 'folder')}:* `{measure['display_folder']}`\n\n"
                        
                        if formatted_dax:
                            doc += "```dax\n" + formatted_dax + "\n```\n\n"
                        
                        if measure.get("format_string"):
                            doc += f"*{get_translation(lang, 'format')}:* `{measure['format_string']}`\n\n"
                        doc += "---\n\n"
                    doc += "\n"
            doc += "\n"

    if cleaned_metadata["relationships"]:
        doc += f"## {get_translation(lang, 'relationships')}\n\n"
        doc += f"| {get_translation(lang, 'from')} | {get_translation(lang, 'to')} | {get_translation(lang, 'type')} | {get_translation(lang, 'direction')} |\n"
        doc += "|------|----|----- |-----------|\n"
        for rel in cleaned_metadata["relationships"]:
            from_str = f"{rel['from_table']}.{rel['from_column']}"
            to_str = f"{rel['to_table']}.{rel['to_column']}"
            doc += f"| {from_str} | {to_str} | {rel['cardinality']} | {rel['cross_filtering']} |\n"
        doc += "\n"

    doc += "---\n\n"
    doc += f"## {get_translation(lang, 'ai_agent_usage_guide')}\n\n"
    doc += f"{get_translation(lang, 'usage_guide_description')}\n\n"
    doc += f"1. {get_translation(lang, 'usage_guide_1')}\n"
    doc += f"2. {get_translation(lang, 'usage_guide_2')}\n"
    doc += f"3. {get_translation(lang, 'usage_guide_3')}\n"
    doc += f"4. {get_translation(lang, 'usage_guide_4')}\n\n"
    doc += f"### {get_translation(lang, 'key_measures_available')}\n\n"

    business_tables = [t for t in cleaned_metadata["tables"] if not t["is_technical"]]
    all_measures_by_category: Dict[str, List[dict]] = {}
    for table in business_tables:
        for measure in table["measures"]:
            if not measure["is_hidden"]:
                all_measures_by_category.setdefault(measure.get("category", "other"), []).append(
                    {
                        "name": measure["name"],
                        "table": table["name"],
                        "expression": measure.get("expression", ""),
                        "format": measure.get("format_string", ""),
                    }
                )

    category_icons = {
        "revenue": "",
        "cost": "",
        "margin": "",
        "percentage": "",
        "ratio": "",
        "temporal": "",
        "calendar_intelligence": "",
        "aggregation": "",
        "filtering": "",
        "other": "",
    }
    for category in ["revenue", "cost", "margin", "percentage", "ratio", "temporal", "other"]:
        if category in all_measures_by_category:
            measures = all_measures_by_category[category][:5]
            if measures:
                category_name = get_category_name(lang, category)
                doc += f"\n#### {category_name}:\n\n"
                for measure in measures:
                    # Translate "from" based on language
                    from_text = get_translation(lang, "from").lower()
                    doc += f"- **{measure['name']}** ({from_text} {measure['table']})\n"
                    if measure["format"]:
                        doc += f"  - {get_translation(lang, 'format')}: `{measure['format']}`\n"
                    doc += "\n"
    return doc


def build_agent_context(cleaned_metadata: dict, lang: str = "en") -> dict:
    """Builds JSON context for agents/LLMs with formatted DAX."""
    summary = cleaned_metadata["summary"]
    business_tables = [t for t in cleaned_metadata["tables"] if not t["is_technical"]]

    # Top 20 most important measures for agents
    all_measures = []
    for table in business_tables:
        for measure in table.get("measures", []):
            if not measure["is_hidden"]:
                expression = measure.get("expression", "")
                formatted_dax = format_dax_for_json(expression)
                complexity = categorize_dax_complexity(expression)
                
                all_measures.append({
                    "name": measure["name"],
                    "table": table["name"],
                    "expression": expression,
                    "formatted_expression": formatted_dax,
                    "category": measure.get("category", "other"),
                    "complexity": complexity,
                    "format_string": measure.get("format_string", ""),
                })

    # Sort by category importance
    category_priority = {
        "revenue": 1, "cost": 2, "margin": 3, "percentage": 4, 
        "ratio": 5, "temporal": 6, "aggregation": 7, "filtering": 8, 
        "calendar_intelligence": 9, "other": 10
    }
    all_measures.sort(key=lambda x: (category_priority.get(x["category"], 10), x["name"]))

    # Identify temporal columns
    temporal_columns = []
    for table in business_tables:
        for col in table.get("columns", []):
            if col.get("category") == "temporal" and not col["is_hidden"]:
                temporal_columns.append({
                    "name": col["name"],
                    "table": table["name"],
                    "data_type": col["data_type"]
                })

    # Generate sample questions (translated)
    sample_questions = [
        get_translation(lang, "sample_question_1"),
        get_translation(lang, "sample_question_2"),
        get_translation(lang, "sample_question_3"),
        get_translation(lang, "sample_question_4"),
        get_translation(lang, "sample_question_5"),
        get_translation(lang, "sample_question_6"),
        get_translation(lang, "sample_question_7"),
    ]

    return {
        "model_name": cleaned_metadata["file_name"],
        "summary": {
            "total_tables": summary["business_tables"],
            "total_measures": summary["total_measures"],
            "total_relationships": summary["total_relationships"],
            "compatibility_level": cleaned_metadata.get("compatibility_level", "unknown")
        },
        "key_measures": all_measures[:20],  # Top 20
        "temporal_columns": temporal_columns,
        "sample_questions": sample_questions,
        "extraction_date": cleaned_metadata.get("extraction_date", ""),
        "usage_notes": [
            get_translation(lang, "agent_usage_note_1"),
            get_translation(lang, "agent_usage_note_2"),
            get_translation(lang, "agent_usage_note_3"),
            get_translation(lang, "agent_usage_note_4"),
            get_translation(lang, "agent_usage_note_5"),
            get_translation(lang, "agent_usage_note_6"),
        ]
    }
