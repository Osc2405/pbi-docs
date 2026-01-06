from pathlib import Path

from pbi_extractor.processor import process_schema
from pbi_extractor.jsonl_generator import generate_model_context
from pbi_extractor.documentation import generate_markdown, build_agent_context


def _minimal_schema():
    return {
        "compatibilityLevel": 1603,
        "model": {
            "tables": [
                {
                    "name": "Sales",
                    "isHidden": False,
                    "columns": [
                        {
                            "name": "OrderDate",
                            "dataType": "dateTime",
                            "isHidden": False,
                        },
                        {
                            "name": "CustomerID",
                            "dataType": "int64",
                            "isHidden": False,
                        },
                    ],
                    "measures": [
                        {
                            "name": "Total Sales",
                            "expression": "SUM(Sales[Amount])",
                            "formatString": "$#,0",
                            "isHidden": False,
                            "displayFolder": "Revenue",
                        }
                    ],
                }
            ],
            "relationships": [
                {
                    "name": "Sales_Customer",
                    "fromTable": "Sales",
                    "fromColumn": "CustomerID",
                    "toTable": "Customer",
                    "toColumn": "CustomerID",
                    "fromCardinality": "many",
                    "toCardinality": "one",
                    "crossFilteringBehavior": "OneDirection",
                    "isActive": True,
                }
            ],
        },
    }


def test_process_schema_basic_counts():
    schema = _minimal_schema()
    metadata = process_schema(schema, "SalesModel.pbit")

    assert metadata["file_name"] == "SalesModel"
    summary = metadata["summary"]

    # 1 business table, 0 technical, 2 visible columns, 1 visible measure, 1 relationship
    assert summary["total_tables"] == 1
    assert summary["business_tables"] == 1
    assert summary["technical_tables"] == 0
    assert summary["total_columns"] == 2
    assert summary["total_measures"] == 1
    assert summary["total_relationships"] == 1

    # Relationship correctly transformed
    assert metadata["relationships"][0]["cardinality"] == "many:one"
    assert metadata["relationships"][0]["from_table"] == "Sales"


def test_generate_markdown_and_agent_context():
    schema = _minimal_schema()
    metadata = process_schema(schema, "SalesModel.pbit")

    # Test English (default)
    md = generate_markdown(metadata)
    assert "# SalesModel - Power BI Data Model" in md
    assert "Total Sales" in md
    assert "Relationships" in md
    assert "Model Summary" in md
    assert "Business Tables" in md

    agent_ctx = build_agent_context(metadata)
    assert agent_ctx["model_name"] == "SalesModel"
    assert agent_ctx["summary"]["total_measures"] == 1
    assert agent_ctx["key_measures"]
    assert any(q for q in agent_ctx["sample_questions"])


def test_generate_markdown_spanish():
    """Test that markdown generation works with Spanish language."""
    schema = _minimal_schema()
    metadata = process_schema(schema, "SalesModel.pbit")

    # Test Spanish
    md = generate_markdown(metadata, lang="es")
    assert "# SalesModel - Modelo de Datos de Power BI" in md
    assert "Total Sales" in md  # Measure names are not translated
    assert "Relaciones" in md
    assert "Resumen del Modelo" in md
    assert "Tablas de Negocio" in md


def test_build_agent_context_spanish():
    """Test that agent context generation works with Spanish language."""
    schema = _minimal_schema()
    metadata = process_schema(schema, "SalesModel.pbit")

    # Test Spanish
    agent_ctx = build_agent_context(metadata, lang="es")
    assert agent_ctx["model_name"] == "SalesModel"
    assert agent_ctx["summary"]["total_measures"] == 1
    
    # Check that sample questions are in Spanish
    questions = agent_ctx["sample_questions"]
    assert any("¿" in q or "Cuáles" in q or "Qué" in q for q in questions)
    
    # Check that usage notes are in Spanish
    usage_notes = agent_ctx["usage_notes"]
    assert len(usage_notes) > 0
    assert any("metadatos" in note.lower() or "modelo" in note.lower() for note in usage_notes)


def test_generate_model_context_jsonl_entries():
    schema = _minimal_schema()
    metadata = process_schema(schema, "SalesModel.pbit")

    entries = generate_model_context(metadata)

    # Should have at least: 1 model, 1 table, 1 measure, 1 relationship
    types = {e["type"] for e in entries}
    assert "model" in types
    assert "table" in types
    assert "measure" in types
    assert "relationship" in types

    # Model overview consistent with summary
    model_entry = next(e for e in entries if e["type"] == "model")
    assert model_entry["summary"]["total_measures"] == 1


