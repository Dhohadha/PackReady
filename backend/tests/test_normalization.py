import inspect
import pytest

from app.product_knowledge import normalization
from app.product_knowledge.normalization import (
    strip_diacritics,
    normalize_text,
    normalize_brand,
    normalize_product_name,
    extract_unit_quantity,
)


def test_strip_diacritics_generic_unicode():
    assert strip_diacritics("Nestlé") == "Nestle"
    assert strip_diacritics("Nescafé") == "Nescafe"
    assert strip_diacritics("Crème Brûlée") == "Creme Brulee"
    assert strip_diacritics("München") == "Munchen"
    assert strip_diacritics("Plain ASCII") == "Plain ASCII"


def test_normalize_brand():
    # None & empty
    assert normalize_brand(None) is None
    assert normalize_brand("") is None
    assert normalize_brand("   ") is None

    # ASCII and whitespace collapsing
    assert normalize_brand("  nestle  ") == "Nestle"
    assert normalize_brand("PARLE   AGRO") == "Parle Agro"

    # Diacritics generic handling
    assert normalize_brand("Nestlé") == "Nestle"
    assert normalize_brand("NESCAFÉ") == "Nescafe"

    # Punctuation preservation
    assert normalize_brand("Coca-Cola") == "Coca-Cola"
    assert normalize_brand("M&M's") == "M&M's"
    assert normalize_brand("7UP") == "7Up"


def test_normalize_product_name():
    # None & empty
    assert normalize_product_name(None) is None
    assert normalize_product_name("") is None
    assert normalize_product_name("   ") is None

    # Conservative whitespace & punctuation preservation
    assert normalize_product_name("  Milkybar  Create  (42g)  ") == "Milkybar Create (42g)"
    assert normalize_product_name("Dettol - Handwash Original 250ml") == "Dettol - Handwash Original 250ml"


def test_extract_unit_quantity():
    # None & empty
    assert extract_unit_quantity(None) == (None, None)
    assert extract_unit_quantity("") == (None, None)
    assert extract_unit_quantity("   ") == (None, None)

    # Numeric inputs
    assert extract_unit_quantity(42) == (42.0, "pcs")
    assert extract_unit_quantity(250.5) == (250.5, "pcs")

    # String parsing
    assert extract_unit_quantity("42g") == (42.0, "g")
    assert extract_unit_quantity("500 ml") == (500.0, "ml")
    assert extract_unit_quantity("1.5 L") == (1.5, "l")
    assert extract_unit_quantity("250 pcs") == (250.0, "pcs")


def test_no_brand_specific_hardcoded_rules():
    source_code = inspect.getsource(normalization)

    # Assert that source code does not contain hardcoded brand names or replacement maps
    forbidden_terms = ["Nestlé", "Nestle", "Nescafé", "Nescafe", "Coca-Cola", "Amul", "Parle"]
    for term in forbidden_terms:
        assert term not in source_code, f"Found forbidden hardcoded brand rule '{term}' in normalization.py!"
