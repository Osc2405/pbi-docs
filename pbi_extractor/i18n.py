"""
Internationalization support for pbi-docs.
Provides translations for documentation strings.
"""

from typing import Dict

# Translation dictionaries
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        # Headers
        "power_bi_data_model": "Power BI Data Model",
        "generated": "Generated",
        "model_summary": "Model Summary",
        "business_tables": "Business Tables",
        "total_columns": "Total Columns",
        "total_measures": "Total Measures",
        "relationships": "Relationships",
        "tables_and_measures": "Tables and Measures",
        "hidden_table_measures_only": "Hidden Table - Measures Only",
        "columns": "Columns",
        "column": "Column",
        "type": "Type",
        "category": "Category",
        "measures": "Measures",
        "from": "From",
        "to": "To",
        "direction": "Direction",
        "ai_agent_usage_guide": "AI Agent Usage Guide",
        "usage_guide_description": "This document describes a Power BI data model. You can use this information to:",
        "usage_guide_1": "Answer business questions about available data",
        "usage_guide_2": "Suggest which measures to use for specific analyses",
        "usage_guide_3": "Explain relationships between tables",
        "usage_guide_4": "Help users understand the data structure",
        "key_measures_available": "Key Measures Available:",
        "folder": "Folder",
        "format": "Format",
        "complexity_simple": "simple",
        "complexity_medium": "medium",
        "complexity_complex": "complex",
        
        # Category names
        "category_revenue": "Revenue Measures",
        "category_cost": "Cost Measures",
        "category_margin": "Margin Measures",
        "category_percentage": "Percentage Measures",
        "category_ratio": "Ratio Measures",
        "category_temporal": "Time-based Measures",
        "category_calendar_intelligence": "Calendar Intelligence",
        "category_aggregation": "Aggregation Measures",
        "category_filtering": "Filtering Measures",
        "category_other": "Other Measures",
        
        # Agent context
        "agent_usage_note_1": "This context contains Power BI model metadata for AI analysis",
        "agent_usage_note_2": "Measures are ordered by business importance",
        "agent_usage_note_3": "DAX expressions are formatted for better readability",
        "agent_usage_note_4": "The 'complexity' field indicates the complexity of each measure",
        "agent_usage_note_5": "Temporal columns are useful for trend analysis",
        "agent_usage_note_6": "Use relationships to understand the model structure",
        
        # Sample questions
        "sample_question_1": "What are the main measures in this model?",
        "sample_question_2": "What tables are related to sales?",
        "sample_question_3": "How is profit margin calculated?",
        "sample_question_4": "What temporal columns are available?",
        "sample_question_5": "What are the relationships between tables?",
        "sample_question_6": "Which measures are more complex to understand?",
        "sample_question_7": "How can I use revenue measures in my analysis?",
    },
    "es": {
        # Headers
        "power_bi_data_model": "Modelo de Datos de Power BI",
        "generated": "Generado",
        "model_summary": "Resumen del Modelo",
        "business_tables": "Tablas de Negocio",
        "total_columns": "Total de Columnas",
        "total_measures": "Total de Medidas",
        "relationships": "Relaciones",
        "tables_and_measures": "Tablas y Medidas",
        "hidden_table_measures_only": "Tabla Oculta - Solo Medidas",
        "columns": "Columnas",
        "column": "Columna",
        "type": "Tipo",
        "category": "Categoría",
        "measures": "Medidas",
        "from": "Desde",
        "to": "Hacia",
        "direction": "Dirección",
        "ai_agent_usage_guide": "Guía de Uso para Agentes de IA",
        "usage_guide_description": "Este documento describe un modelo de datos de Power BI. Puedes usar esta información para:",
        "usage_guide_1": "Responder preguntas de negocio sobre los datos disponibles",
        "usage_guide_2": "Sugerir qué medidas usar para análisis específicos",
        "usage_guide_3": "Explicar las relaciones entre tablas",
        "usage_guide_4": "Ayudar a los usuarios a entender la estructura de datos",
        "key_measures_available": "Medidas Clave Disponibles:",
        "folder": "Carpeta",
        "format": "Formato",
        "complexity_simple": "simple",
        "complexity_medium": "medio",
        "complexity_complex": "complejo",
        
        # Category names
        "category_revenue": "Medidas de Ingresos",
        "category_cost": "Medidas de Costos",
        "category_margin": "Medidas de Margen",
        "category_percentage": "Medidas de Porcentaje",
        "category_ratio": "Medidas de Razón",
        "category_temporal": "Medidas Temporales",
        "category_calendar_intelligence": "Inteligencia de Calendario",
        "category_aggregation": "Medidas de Agregación",
        "category_filtering": "Medidas de Filtrado",
        "category_other": "Otras Medidas",
        
        # Agent context
        "agent_usage_note_1": "Este contexto contiene metadatos del modelo de Power BI para análisis con IA",
        "agent_usage_note_2": "Las medidas están ordenadas por importancia de negocio",
        "agent_usage_note_3": "Las expresiones DAX están formateadas para mejor legibilidad",
        "agent_usage_note_4": "El campo 'complexity' indica la complejidad de cada medida",
        "agent_usage_note_5": "Las columnas temporales son útiles para análisis de tendencias",
        "agent_usage_note_6": "Usa las relaciones para entender la estructura del modelo",
        
        # Sample questions
        "sample_question_1": "¿Cuáles son las principales medidas en este modelo?",
        "sample_question_2": "¿Qué tablas están relacionadas con ventas?",
        "sample_question_3": "¿Cómo se calcula el margen de ganancia?",
        "sample_question_4": "¿Qué columnas temporales están disponibles?",
        "sample_question_5": "¿Cuáles son las relaciones entre tablas?",
        "sample_question_6": "¿Qué medidas son más complejas de entender?",
        "sample_question_7": "¿Cómo puedo usar las medidas de ingresos en mi análisis?",
    }
}


def get_translation(lang: str, key: str, default: str = None) -> str:
    """
    Get translation for a given key in the specified language.
    
    Args:
        lang: Language code ('en' or 'es')
        key: Translation key
        default: Default value if key not found (uses key as fallback)
        
    Returns:
        Translated string
    """
    if lang not in TRANSLATIONS:
        lang = "en"  # Fallback to English
    
    translation = TRANSLATIONS.get(lang, {}).get(key, default or key)
    return translation


def get_category_name(lang: str, category: str) -> str:
    """
    Get translated category name.
    
    Args:
        lang: Language code
        category: Category key (e.g., 'revenue', 'cost')
        
    Returns:
        Translated category name
    """
    key = f"category_{category}"
    default = category.title() + " Measures" if lang == "en" else category.title() + " Medidas"
    return get_translation(lang, key, default)


def get_complexity_label(lang: str, complexity: str) -> str:
    """
    Get translated complexity label.
    
    Args:
        lang: Language code
        complexity: Complexity level ('simple', 'medium', 'complex')
        
    Returns:
        Translated complexity label
    """
    key = f"complexity_{complexity}"
    return get_translation(lang, key, complexity)

