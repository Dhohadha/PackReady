import re
import unicodedata
from typing import Optional, Tuple, Any
from app.products.resolver import normalize_identifier_value


def strip_diacritics(text: str) -> str:
    """
    Generically normalizes Unicode text by decomposing characters (NFKD)
    and removing combining diacritical marks (Category 'Mn').
    Works for any language/script without company-specific lookup tables.
    """
    nfkd_form = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd_form if unicodedata.category(c) != "Mn")


def normalize_text(val: Optional[str]) -> Optional[str]:
    """
    Safe whitespace normalization and canonical Unicode composition (NFC).
    """
    if not val:
        return None
    cleaned = re.sub(r"\s+", " ", val.strip())
    if not cleaned:
        return None
    return unicodedata.normalize("NFC", cleaned)


def normalize_brand(brand: Optional[str]) -> Optional[str]:
    """
    Generic brand normalization:
    - Collapses whitespace
    - Generically normalizes diacritics via Unicode NFKD
    - Normalizes case when all upper or all lower, preserving mixed-case brands
    """
    text = normalize_text(brand)
    if not text:
        return None
    normalized = strip_diacritics(text)
    if normalized.isupper() or normalized.islower():
        return normalized.title()
    return normalized


def normalize_product_name(name: Optional[str]) -> Optional[str]:
    """
    Conservative product name normalization preserving meaningful display characters
    and canonical Unicode NFC representation.
    """
    return normalize_text(name)


def extract_unit_quantity(raw_val: Any) -> Tuple[Optional[float], Optional[str]]:
    """
    Extracts numeric value and unit measurement string from raw strings or numeric values.
    """
    if raw_val is None:
        return None, None

    if isinstance(raw_val, (int, float)):
        return float(raw_val), "pcs"

    s = str(raw_val).strip()
    if not s:
        return None, None

    # Match number followed by unit e.g. "42g", "500 ml", "1.5L", "250 pcs"
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?$", s)
    if match:
        num_str, unit_str = match.groups()
        val = float(num_str)
        unit = unit_str.lower() if unit_str else "pcs"
        return val, unit

    return None, None
