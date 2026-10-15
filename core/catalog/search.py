"""Retrieval helpers grounded in the current product catalog."""
from __future__ import annotations
from typing import Any
from core.catalog.repository import CatalogRepository

def search_catalog(repository: CatalogRepository, *, tenant_id: str, query: str, limit: int = 5) -> list[dict[str, Any]]:
    if not query.strip():
        return []
    return repository.search(tenant_id=tenant_id, query=query, limit=limit)

def format_catalog_results(products: list[dict[str, Any]]) -> str:
    if not products:
        return "لا توجد نتيجة مؤكدة في الكتالوج. لا تخمّن السعر أو التوفر؛ اطلب مراجعة المسؤول."
    lines = []
    for p in products:
        price = f"{p['price']} {p['currency']}" if p.get('price') is not None else "السعر غير مسجل"
        lines.append(f"{p['sku']} — {p['title']} — {price} — التوفر: {p['availability']}")
        attrs = p.get('attributes') or {}
        if attrs.get('colors'):
            lines.append("الألوان: " + "، ".join(attrs['colors']))
        if attrs.get('sizes'):
            lines.append("المقاسات: " + ("جميع المقاسات" if attrs.get('all_sizes_available') else "، ".join(attrs['sizes'])))
    return "\n".join(lines)
