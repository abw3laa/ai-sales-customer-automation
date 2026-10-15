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
