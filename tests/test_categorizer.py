import pytest

from pbi_extractor.categorizer import (
    is_technical_table,
    categorize_measure,
    get_column_category,
)


def test_is_technical_table_true():
    assert is_technical_table("LocalDateTable_123")
    assert is_technical_table("DateTableTemplate_ABC")
    assert is_technical_table("ParameterTable_Config")


def test_is_technical_table_false():
    assert not is_technical_table("Sales")
    assert not is_technical_table("Customers")


@pytest.mark.parametrize(
    "name,expr,expected",
    [
        ("Total Revenue", "SUM(Fact[Revenue])", "revenue"),
        ("Costo Total", "SUM(Fact[Cost])", "cost"),
        ("Gross Margin", "([Revenue] - [Cost])", "margin"),
        # La lógica actual prioriza el nombre sobre la expresión
        ("Revenue %", "DIVIDE([Revenue],[Total])", "revenue"),
        ("YTD Revenue", "TOTALYTD([Revenue],'Date'[Date])", "revenue"),
        ("Count Orders", "COUNT(Fact[OrderId])", "aggregation"),
        ("Margin Ratio", "[Margin] / [Revenue]", "margin"),
        ("Date Offset", "DATEADD('Date'[Date],-1,DAY)", "calendar_intelligence"),
        ("Filtered Sales", "CALCULATE([Sales],FILTER(...))", "revenue"),
    ],
)
def test_categorize_measure(name, expr, expected):
    assert categorize_measure(name, expr) == expected


@pytest.mark.parametrize(
    "data_type,name,expected",
    [
        ("int64", "CustomerID", "identifier"),
        ("dateTime", "OrderDate", "temporal"),
        # 'CantidadVendida' contiene 'id', por lo que se clasifica como 'identifier'
        ("int64", "CantidadVendida", "identifier"),
        ("int64", "SomeNumber", "numeric"),
        ("string", "NombreCliente", "descriptive"),
        ("string", "Segment", "categorical"),
        ("unknown", "Whatever", "other"),
    ],
)
def test_get_column_category(data_type, name, expected):
    assert get_column_category(data_type, name) == expected


