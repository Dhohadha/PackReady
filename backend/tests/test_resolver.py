import pytest
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.products.models import Category, Product, ProductIdentifier, IdentifierType
from app.products.resolver import (
    ProductResolver,
    ProductNotFoundError,
    normalize_identifier_value,
)


@pytest.fixture(scope="function")
def db_session() -> Session:
    """
    Fixture to provide a database session and clean up the test tables.
    """
    session = SessionLocal()
    session.query(ProductIdentifier).delete()
    session.query(Product).delete()
    session.query(Category).delete()
    session.commit()
    
    try:
        yield session
    finally:
        session.query(ProductIdentifier).delete()
        session.query(Product).delete()
        session.query(Category).delete()
        session.commit()
        session.close()


def test_normalize_identifier_value() -> None:
    # 1. Valid normalization with formatting
    assert normalize_identifier_value("  400-638.133_3931 \t ") == "4006381333931"
    
    # 2. Preserves leading zeros
    assert normalize_identifier_value(" 00123-456 ") == "00123456"

    # 3. None / Null raises ValueError
    with pytest.raises(ValueError, match="cannot be null"):
        normalize_identifier_value(None)

    # 4. Empty value raises ValueError
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_identifier_value("")
    with pytest.raises(ValueError, match="cannot be empty"):
        normalize_identifier_value("   ")

    # 5. Spacing-only characters raises ValueError
    with pytest.raises(ValueError, match="must contain valid characters"):
        normalize_identifier_value(" - - - ")

    # 6. Alphabetic/Non-numeric character raises ValueError
    with pytest.raises(ValueError, match="must contain only numeric digits"):
        normalize_identifier_value("123A456")


def test_resolver_success(db_session: Session) -> None:
    # Create category, product and identifier
    cat = Category(name="Drinks")
    db_session.add(cat)
    db_session.commit()

    prod = Product(name="Soda Can", category_id=cat.id)
    db_session.add(prod)
    db_session.commit()

    ident = ProductIdentifier(
        product_id=prod.id,
        identifier_type=IdentifierType.EAN,
        value="1234567890128"
    )
    db_session.add(ident)
    db_session.commit()

    # Resolve using resolver
    resolved_prod = ProductResolver.resolve_by_identifier(
        db=db_session,
        identifier_type="EAN",
        value=" 123-456.789-0128 "
    )
    assert resolved_prod.id == prod.id
    assert resolved_prod.name == "Soda Can"


def test_resolver_invalid_type(db_session: Session) -> None:
    with pytest.raises(ValueError, match="Invalid identifier type"):
        ProductResolver.resolve_by_identifier(
            db=db_session,
            identifier_type="ISBN",
            value="123456789012"
        )


def test_resolver_invalid_value_format(db_session: Session) -> None:
    with pytest.raises(ValueError, match="must contain only numeric digits"):
        ProductResolver.resolve_by_identifier(
            db=db_session,
            identifier_type="EAN",
            value="123A456"
        )


def test_resolver_not_found(db_session: Session) -> None:
    # Query non-existent EAN
    with pytest.raises(ProductNotFoundError, match="not found"):
        ProductResolver.resolve_by_identifier(
            db=db_session,
            identifier_type="EAN",
            value="999999999999"
        )
