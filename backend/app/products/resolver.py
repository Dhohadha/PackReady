from sqlalchemy.orm import Session
from app.products.models import Product, ProductIdentifier, IdentifierType
from app.products.exceptions import ProductNotFoundError


def normalize_identifier_value(v: str) -> str:
    if v is None:
        raise ValueError("Identifier value cannot be null")
    v_trimmed = v.strip()
    if not v_trimmed:
        raise ValueError("Identifier value cannot be empty")
    normalized = "".join(c for c in v_trimmed if c not in (' ', '-', '.', '_', '\t'))
    if not normalized:
        raise ValueError("Identifier value must contain valid characters")
    if not normalized.isdigit():
        raise ValueError("Identifier value must contain only numeric digits")
    return normalized


class ProductResolver:
    @staticmethod
    def resolve_by_identifier(
        db: Session,
        identifier_type: str,
        value: str,
    ) -> Product:
        """
        Resolves a product by its identifier type and value.
        Raises ValueError if validation fails (e.g. invalid type or empty/invalid format).
        Returns the Product if found.
        Raises ProductNotFoundError if the identifier or product does not exist.
        """
        # 1. Validate identifier_type
        try:
            id_type = IdentifierType(identifier_type.upper())
        except ValueError:
            raise ValueError(
                f"Invalid identifier type '{identifier_type}'. Must be one of EAN, UPC, GTIN."
            )

        # 2. Normalize value
        norm_value = normalize_identifier_value(value)

        # 3. Query
        db_identifier = (
            db.query(ProductIdentifier)
            .filter(
                ProductIdentifier.identifier_type == id_type,
                ProductIdentifier.value == norm_value,
            )
            .first()
        )
        if not db_identifier or not db_identifier.product:
            raise ProductNotFoundError(
                f"Product with identifier {id_type.value}:{norm_value} not found."
            )

        return db_identifier.product
