"""
Functions for categorizing tables, columns and measures.
"""

from typing import Optional


def is_technical_table(table_name: str) -> bool:
    """Identifies technical tables that are not relevant for business."""
    technical_patterns = [
        "LocalDateTable_",
        "DateTableTemplate_",
        "ParameterTable_",
    ]
    for pattern in technical_patterns:
        if table_name.startswith(pattern):
            return True
    return False


def categorize_measure(measure_name: str, expression: Optional[str]) -> str:
    """Categorizes measures based on their name and DAX expression."""
    name_lower = (measure_name or "").lower()
    expr_lower = (expression or "").lower()

    if any(x in name_lower for x in ["revenue", "sales", "ventas", "ingresos"]):
        return "revenue"
    if any(x in name_lower for x in ["cost", "costo", "expense", "gasto"]):
        return "cost"
    if any(x in name_lower for x in ["margin", "margen", "profit", "beneficio"]):
        return "margin"
    if any(x in name_lower for x in ["%", "percent", "porcentaje", "ratio", "rate"]):
        return "percentage"
    if any(x in name_lower for x in ["ytd", "sply", "year", "año", "period"]):
        return "temporal"
    if any(x in name_lower for x in ["count", "total", "sum", "number"]):
        if "sum" in expr_lower or "count" in expr_lower or "total" in expr_lower:
            return "aggregation"
    if "/" in expr_lower or "divide" in expr_lower or "%" in expr_lower:
        return "ratio"
    if any(x in expr_lower for x in ["dateadd", "datesytd", "datesmtd", "datesqtd"]):
        return "calendar_intelligence"
    if any(x in expr_lower for x in ["filter", "all", "selectedvalue", "hasonevalue"]):
        return "filtering"
    return "other"


def get_column_category(data_type: str, column_name: str) -> str:
    """Categorizes columns based on their type and name."""
    name_lower = (column_name or "").lower()
    if any(x in name_lower for x in ["id", "sk.", "ck.", "key"]):
        return "identifier"
    if data_type in ["dateTime", "date"] or "fecha" in name_lower or "date" in name_lower:
        return "temporal"
    if data_type in ["int64", "double", "decimal"]:
        if any(x in name_lower for x in ["cantidad", "monto", "total", "count", "amount"]):
            return "metric"
        return "numeric"
    if data_type == "string":
        if any(x in name_lower for x in ["nombre", "descripcion", "name", "description"]):
            return "descriptive"
        return "categorical"
    return "other"
