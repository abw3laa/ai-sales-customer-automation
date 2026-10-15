from decimal import Decimal
from core.catalog.parser import parse_catalog_post

def test_arabic_product_example():
    parsed = parse_catalog_post("بجامة رياضية adidas\nA100 الكود\nالألوان المتوفرة 7: الأصفر، الأبيض، الأخضر، الأحمر، الأسود، البيج، الذهبي\nالسعر 1200 ₺\nجميع المقاسات متوفرة")
    assert parsed.code == "A100"
    assert parsed.title and "adidas" in parsed.title.lower()
    assert parsed.price == Decimal("1200")
    assert parsed.currency == "TRY"
    assert parsed.attributes["color_count"] == 7
    assert parsed.attributes["all_sizes_available"] is True
    assert parsed.status == "active"

def test_structured_sizes_and_offer_code():
    parsed = parse_catalog_post("Code: A101\nName: Adidas tracksuit\nPrice: 1200 TRY\nSizes: M, L, XL, XXL, S\nColors: black, white")
    assert parsed.code == "A101"
    assert parsed.attributes["sizes"] == ["M", "L", "XL", "XXL", "S"]
    assert parsed.status == "active"

def test_ambiguous_post_needs_review():
    parsed = parse_catalog_post("عرض جميل لفترة محدودة")
    assert parsed.status == "needs_review"
    assert "missing_code" in parsed.warnings
    assert "missing_or_ambiguous_price_currency" in parsed.warnings


def test_offer_dates_are_parsed_only_when_unambiguous():
    parsed = parse_catalog_post(
        """Code: A202
Name: Adidas tracksuit offer
Price: 900 TRY
Offer starts: 2026-10-20
Offer ends: 2026-10-31T23:59:00+03:00"""
    )
    assert parsed.attributes["offer_starts_at"] == "2026-10-20T00:00:00+00:00"
    assert parsed.attributes["offer_ends_at"] == "2026-10-31T20:59:00+00:00"
    assert not any(warning.startswith("invalid_offer_") for warning in parsed.warnings)


def test_ambiguous_offer_datetime_is_flagged_for_review():
    parsed = parse_catalog_post(
        """Code: A203
Name: Limited offer
Price: 900 TRY
Offer ends: 31/10/2026"""
    )
    assert "invalid_offer_end_datetime_use_iso8601_with_timezone" in parsed.warnings
    assert "offer_ends_at" not in parsed.attributes
