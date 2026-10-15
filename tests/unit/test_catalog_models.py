from decimal import Decimal

import pytest

from core.catalog.models import ProductRecord


def test_valid_product_record():
    product = ProductRecord(
        tenant_id="tenant-1",
        sku="SKU-1001",
        title="Demo product",
        price=Decimal("129.90"),
        currency="TRY",
        availability="in_stock",
    )
    product.validate()


def test_price_requires_currency():
    product = ProductRecord(
        tenant_id="tenant-1", sku="SKU-1001", title="Demo product", price=Decimal("10.00")
    )
    with pytest.raises(ValueError, match="price and currency"):
        product.validate()


def test_negative_price_is_rejected():
    product = ProductRecord(
        tenant_id="tenant-1",
        sku="SKU-1001",
        title="Demo product",
        price=Decimal("-1.00"),
        currency="TRY",
    )
    with pytest.raises(ValueError, match="negative"):
        product.validate()


def test_currency_must_be_iso_style_code():
    product = ProductRecord(
        tenant_id="tenant-1",
        sku="SKU-1001",
        title="Demo product",
        price=Decimal("1.00"),
        currency="try",
    )
    with pytest.raises(ValueError, match="three-letter"):
        product.validate()


def test_offer_end_must_follow_start():
    from datetime import datetime, timezone

    start = datetime(2026, 1, 2, tzinfo=timezone.utc)
    end = datetime(2026, 1, 1, tzinfo=timezone.utc)
    product = ProductRecord(
        tenant_id="tenant-1",
        sku="SKU-1001",
        title="Demo product",
        offer_starts_at=start,
        offer_ends_at=end,
    )
    with pytest.raises(ValueError, match="offer_ends_at"):
        product.validate()
