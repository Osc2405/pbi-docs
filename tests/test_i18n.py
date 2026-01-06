"""
Tests for internationalization (i18n) module.
Verifies translation functionality for English and Spanish.
"""

import pytest

from pbi_extractor.i18n import (
    get_translation,
    get_category_name,
    get_complexity_label,
    TRANSLATIONS,
)


def test_get_translation_english():
    """Test that English translations work correctly."""
    assert get_translation("en", "power_bi_data_model") == "Power BI Data Model"
    assert get_translation("en", "generated") == "Generated"
    assert get_translation("en", "model_summary") == "Model Summary"
    assert get_translation("en", "business_tables") == "Business Tables"
    assert get_translation("en", "relationships") == "Relationships"


def test_get_translation_spanish():
    """Test that Spanish translations work correctly."""
    assert get_translation("es", "power_bi_data_model") == "Modelo de Datos de Power BI"
    assert get_translation("es", "generated") == "Generado"
    assert get_translation("es", "model_summary") == "Resumen del Modelo"
    assert get_translation("es", "business_tables") == "Tablas de Negocio"
    assert get_translation("es", "relationships") == "Relaciones"


def test_get_translation_fallback():
    """Test that invalid language falls back to English."""
    result = get_translation("invalid", "power_bi_data_model")
    assert result == "Power BI Data Model"  # Should fallback to English


def test_get_translation_missing_key():
    """Test that missing translation key returns the key itself."""
    result = get_translation("en", "nonexistent_key")
    assert result == "nonexistent_key"


def test_get_category_name_english():
    """Test category name translation in English."""
    assert get_category_name("en", "revenue") == "Revenue Measures"
    assert get_category_name("en", "cost") == "Cost Measures"
    assert get_category_name("en", "margin") == "Margin Measures"
    assert get_category_name("en", "percentage") == "Percentage Measures"


def test_get_category_name_spanish():
    """Test category name translation in Spanish."""
    assert get_category_name("es", "revenue") == "Medidas de Ingresos"
    assert get_category_name("es", "cost") == "Medidas de Costos"
    assert get_category_name("es", "margin") == "Medidas de Margen"
    assert get_category_name("es", "percentage") == "Medidas de Porcentaje"


def test_get_complexity_label_english():
    """Test complexity label translation in English."""
    assert get_complexity_label("en", "simple") == "simple"
    assert get_complexity_label("en", "medium") == "medium"
    assert get_complexity_label("en", "complex") == "complex"


def test_get_complexity_label_spanish():
    """Test complexity label translation in Spanish."""
    assert get_complexity_label("es", "simple") == "simple"
    assert get_complexity_label("es", "medium") == "medio"
    assert get_complexity_label("es", "complex") == "complejo"


def test_translations_completeness():
    """Test that both languages have the same keys."""
    en_keys = set(TRANSLATIONS["en"].keys())
    es_keys = set(TRANSLATIONS["es"].keys())
    
    # Both languages should have the same translation keys
    assert en_keys == es_keys, "English and Spanish translations should have the same keys"
    
    # Verify we have a reasonable number of translations
    assert len(en_keys) > 30, "Should have a reasonable number of translations"


def test_translations_not_empty():
    """Test that translations are not empty strings."""
    for lang in ["en", "es"]:
        for key, value in TRANSLATIONS[lang].items():
            assert value, f"Translation {lang}:{key} should not be empty"

