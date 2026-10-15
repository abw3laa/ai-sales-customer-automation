"""Parse admin-authored Telegram catalog posts without guessing uncertain values."""
from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

_CURRENCY_MAP = {"₺": "TRY", "TL": "TRY", "TRY": "TRY", "USD": "USD", "$": "USD", "EUR": "EUR", "€": "EUR"}
_FIELD_LABELS = {
    "code": ("code", "sku", "الكود", "رمز المنتج", "رقم المنتج", "رقم العرض", "الرمز"),
    "name": ("name", "product", "title", "الاسم", "المنتج", "اسم المنتج", "العرض", "اسم العرض"),
    "price": ("price", "السعر", "السعر الحالي"),
    "colors": ("colors", "colour", "color", "الألوان", "الالوان", "اللون"),
    "sizes": ("sizes", "size", "المقاسات", "المقاس", "الأحجام", "الاحجام"),
    "availability": ("availability", "stock", "التوفر", "الحالة"),
    "description": ("description", "specifications", "details", "الوصف", "المواصفات", "التفاصيل"),
    "offer_starts": ("offer starts", "starts", "بداية العرض", "يبدأ"),
    "offer_ends": ("offer ends", "ends", "نهاية العرض", "ينتهي"),
}
_COLORS = ("الأصفر", "الاصفر", "الأبيض", "الابيض", "الأخضر", "الاخضر", "الأحمر", "الاحمر", "الأسود", "الاسود", "البيج", "الذهبي", "yellow", "white", "green", "red", "black", "beige", "gold")
_SIZES = ("XXXL", "XXL", "XL", "XS", "XXS", "S", "M", "L", "3XL", "2XL")


@dataclass(frozen=True)
class ParsedCatalogPost:
    code: str | None
    title: str | None
    price: Decimal | None
    currency: str | None
    attributes: dict[str, Any]
    availability: str
    status: str
    kind: str
    warnings: tuple[str, ...]
    raw_text: str


def _field_lines(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    labels = [(label.casefold(), key) for key, names in _FIELD_LABELS.items() for label in names]
    for line in text.splitlines():
        clean = line.strip().lstrip("-•* ").strip()
        if not clean:
            continue
        if ":" in clean or "：" in clean:
            label, value = re.split(r"[:：]", clean, maxsplit=1)
            label_norm = label.strip().casefold()
            for candidate, key in labels:
                if label_norm == candidate:
                    found[key] = value.strip()
                    break
    return found


def _price(text: str) -> tuple[Decimal | None, str | None]:
    # Accept examples such as "1200 ₺", "1,200 TRY", "1200.50 TL".
    match = re.search(r"(?<!\w)(\d[\d.,]*)\s*(₺|TL|TRY|USD|\$|EUR|€)(?!\w)", text, re.IGNORECASE)
    if not match:
        # Unicode currency symbols may not have a word boundary after them.
        match = re.search(r"(\d[\d.,]*)\s*(₺|TL|TRY|USD|\$|EUR|€)", text, re.IGNORECASE)
    if not match:
        return None, None
    raw = match.group(1).replace(" ", "")
    if "," in raw and "." in raw:
        raw = raw.replace(",", "") if raw.rfind(".") > raw.rfind(",") else raw.replace(".", "").replace(",", ".")
    elif "," in raw:
        tail = raw.rsplit(",", 1)[1]
        raw = raw.replace(",", ".") if len(tail) in (1, 2) else raw.replace(",", "")
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None, None
    currency = _CURRENCY_MAP.get(match.group(2).upper(), _CURRENCY_MAP.get(match.group(2)))
    return amount, currency


def _list_values(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,،;/|]+", value) if part.strip()]


def parse_catalog_post(text: str, *, caption: str | None = None) -> ParsedCatalogPost:
    """Parse structured fields and common free-form Arabic/English posts.

    The parser intentionally marks missing code, title, or price/currency for review.
    """
    raw = "\n".join(part for part in (text, caption) if part).strip()
    fields = _field_lines(raw)
    code = fields.get("code")
    title = fields.get("name")
    if not code:
        # Inline admin code examples: "A100 الكود" or "الكود A100".
        m = re.search(r"(?:الكود|رمز المنتج|رقم المنتج|رقم العرض|code|sku)\s*[:：-]?\s*([A-Z]{1,5}[-_]?[A-Z0-9]{2,20})", raw, re.I)
        if m:
            code = m.group(1).upper()
        else:
            # A bare all-letter brand such as ADIDAS is not a product SKU.
            # Infer an unlabeled code only when it contains at least one digit.
            m = re.search(
                r"\b(?=[A-Z0-9_-]*[0-9])[A-Z]{1,5}[-_]?[A-Z0-9]{2,20}\b",
                raw,
            )
            if m:
                code = m.group(0).upper()
    if not title:
        for line in raw.splitlines():
            candidate = line.strip().lstrip("-•* ").strip()
            if not candidate or ":" in candidate or re.search(r"\d[\d.,]*\s*(₺|TL|TRY|USD|\$|EUR|€)", candidate, re.I):
                continue
            if re.search(r"(بجامة|قميص|بنطال|حذاء|فستان|adidas|nike|product|offer|عرض|منتج)", candidate, re.I):
                title = candidate
                break
    price, currency = _price(fields.get("price", raw))
    colors = _list_values(fields["colors"]) if fields.get("colors") else []
    sizes = _list_values(fields["sizes"]) if fields.get("sizes") else []
    if not colors:
        colors = [c for c in _COLORS if re.search(rf"(?<!\w){re.escape(c)}(?!\w)", raw, re.I)]
    if not sizes:
        size_text = re.search(r"(?:المقاسات|المقاس|sizes?|sizes available)\s*[:：-]?\s*([A-Z0-9 .,/،-]+)", raw, re.I)
        if size_text:
            sizes = [s.upper() for s in re.findall(r"(?<![A-Z0-9])(?:XXXL|XXL|XXS|XL|XS|3XL|2XL|S|M|L)(?![A-Z0-9])", size_text.group(1), re.I)]
    all_sizes = bool(re.search(r"(جميع المقاسات|كل المقاسات|all sizes|all sizes available)", raw, re.I))
    if all_sizes:
        sizes = ["all"]
    availability = "in_stock" if re.search(r"(متوفر|متوفرة|متاح|متاحة|in stock|available)", raw, re.I) else "unknown"
    if re.search(r"(نفد|غير متوفر|out of stock|sold out)", raw, re.I):
        availability = "out_of_stock"
    kind = "offer" if re.search(r"(عرض|خصم|تخفيض|offer|discount|promotion)", raw, re.I) else "product"
    warnings: list[str] = []
    if not code:
        warnings.append("missing_code")
    if not title:
        warnings.append("missing_title")
    if price is None or currency is None:
        warnings.append("missing_or_ambiguous_price_currency")
    if kind == "offer" and not (fields.get("offer_starts") or fields.get("offer_ends")):
        warnings.append("offer_validity_not_specified")
    attributes: dict[str, Any] = {"kind": kind}
    if colors:
        attributes["colors"] = list(dict.fromkeys(colors))
        attributes["color_count"] = len(attributes["colors"])
    if sizes:
        attributes["sizes"] = list(dict.fromkeys(sizes))
        attributes["all_sizes_available"] = "all" in sizes
    if fields.get("description"):
        attributes["specifications"] = fields["description"]
    if fields.get("offer_starts"):
        attributes["offer_starts_text"] = fields["offer_starts"]
    if fields.get("offer_ends"):
        attributes["offer_ends_text"] = fields["offer_ends"]
    status = "active" if not any(w in warnings for w in ("missing_code", "missing_title", "missing_or_ambiguous_price_currency")) else "needs_review"
    return ParsedCatalogPost(code, title, price, currency, attributes, availability, status, kind, tuple(warnings), raw)
