"""Tenant-scoped product lookup helpers for operator commands."""
from __future__ import annotations
import os
from typing import Any

def _format_product(p: dict[str, Any]) -> str:
    price = f"{p['price']} {p['currency']}" if p.get("price") is not None else "السعر غير مسجل"
    lines = [f"{p.get('sku')} — {p.get('title')}", f"السعر: {price}", f"التوفر: {p.get('availability', 'unknown')}"]
    attrs = p.get("attributes") or {}
    if attrs.get("colors"):
        lines.append("الألوان: " + "، ".join(attrs["colors"]))
    if attrs.get("sizes"):
        lines.append("المقاسات: " + ("جميع المقاسات" if attrs.get("all_sizes_available") else "، ".join(attrs["sizes"])))
    return "\n".join(lines)

def lookup_product(sku: str, *, tenant_id: str, database_url: str | None = None) -> str:
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    if not sku.strip():
        return "استخدم: /product A100"
    import psycopg
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT sku, title, description, price::text, currency, availability, attributes
                FROM products WHERE tenant_id=%s::uuid AND sku=%s AND status='active'
                AND (offer_ends_at IS NULL OR offer_ends_at > now())""", (tenant_id, sku.strip()))
            row = cur.fetchone()
    if not row:
        return "لم يُعثر على منتج نشط بهذا الكود."
    keys = ("sku", "title", "description", "price", "currency", "availability", "attributes")
    return _format_product(dict(zip(keys, row, strict=True)))

def search_products(query: str, *, tenant_id: str, database_url: str | None = None, limit: int = 5) -> str:
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    if not query.strip():
        return "استخدم: /search adidas"
    import psycopg
    needle = f"%{query.strip()}%"
    limit = max(1, min(int(limit), 10))
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT sku, title, description, price::text, currency, availability, attributes
                FROM products WHERE tenant_id=%s::uuid AND status='active'
                AND (offer_ends_at IS NULL OR offer_ends_at > now())
                AND (sku ILIKE %s OR title ILIKE %s OR COALESCE(description,'') ILIKE %s OR attributes::text ILIKE %s)
                ORDER BY updated_at DESC LIMIT %s""",
                (tenant_id, needle, needle, needle, needle, limit))
            rows = cur.fetchall()
    keys = ("sku", "title", "description", "price", "currency", "availability", "attributes")
    if not rows:
        return "لا توجد نتائج مؤكدة؛ لا تخمّن السعر أو التوفر."
    return "\n\n".join(_format_product(dict(zip(keys, row, strict=True))) for row in rows)
