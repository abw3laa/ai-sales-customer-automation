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


def list_review_products(*, tenant_id: str, database_url: str | None = None, limit: int = 10) -> str:
    """List products awaiting a human decision, scoped to one tenant."""
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    import psycopg

    limit = max(1, min(int(limit), 20))
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT sku, title, price::text, currency, availability
                FROM products WHERE tenant_id=%s::uuid AND status='needs_review'
                ORDER BY updated_at DESC LIMIT %s""",
                (tenant_id, limit),
            )
            rows = cur.fetchall()
    lines = ["المنتجات التي تحتاج إلى مراجعة:"]
    for sku, title, price, currency, availability in rows:
        shown_price = f"{price} {currency}" if price is not None and currency else "السعر/العملة غير مكتملين"
        lines.append(f"{sku} — {title} | {shown_price} | التوفر: {availability}")

    # Posts missing a SKU/title are held separately because they cannot satisfy
    # products.sku/title constraints. Operators can edit the original channel post.
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT source_message_id, proposed_sku, proposed_title, warnings
                FROM product_review_queue
                WHERE tenant_id=%s::uuid AND status='needs_review'
                ORDER BY created_at DESC LIMIT %s""",
                (tenant_id, min(limit, 20)),
            )
            incomplete_rows = cur.fetchall()
    for message_id, sku, title, warnings in incomplete_rows:
        missing = []
        if not sku:
            missing.append("الكود")
        if not title:
            missing.append("اسم المنتج")
        lines.append(
            f"منشور Telegram #{message_id} — بيانات ناقصة: {', '.join(missing) or 'تحقق يدوي'}"
        )
    if len(lines) == 1:
        return "لا توجد منتجات أو منشورات بانتظار المراجعة."
    lines.append("للاعتماد: /approve <SKU> — للرفض: /reject <SKU> <السبب>")
    lines.append("المنشورات ذات الكود/الاسم الناقص: عدّل المنشور الأصلي ثم أعد إرساله؛ لا تُنشر تلقائيًا.")
    return "\n".join(lines)


def review_product(
    sku: str, *, tenant_id: str, telegram_user_id: int, approve: bool,
    reason: str = "", database_url: str | None = None,
) -> str:
    """Approve or archive a reviewed product and write an audit record atomically."""
    url = database_url or os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    if not sku.strip():
        return "استخدم /approve <SKU> أو /reject <SKU> <السبب>."
    import psycopg

    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT title, price, currency, status FROM products
                WHERE tenant_id=%s::uuid AND sku=%s FOR UPDATE""",
                (tenant_id, sku.strip()),
            )
            row = cur.fetchone()
            if not row or row[3] != "needs_review":
                return "لم يُعثر على منتج بهذا الكود يحتاج إلى مراجعة."
            title, price, currency, _status = row
            if approve and (price is None or not currency):
                return "لا يمكن اعتماد المنتج قبل تسجيل السعر والعملة الصحيحين."
            new_status = "active" if approve else "archived"
            cur.execute(
                """UPDATE products SET status=%s, updated_at=now(), last_verified_at=now()
                WHERE tenant_id=%s::uuid AND sku=%s""",
                (new_status, tenant_id, sku.strip()),
            )
            cur.execute(
                """INSERT INTO operator_audit_log
                (tenant_id, telegram_user_id, action, target_type, target_id, result, metadata)
                VALUES (%s::uuid, %s, %s, 'product', %s, 'success', %s::jsonb)""",
                (tenant_id, str(telegram_user_id), "approve_product" if approve else "reject_product",
                 sku.strip(), __import__("json").dumps({"reason": reason[:500], "title": title}, ensure_ascii=False)),
            )
    return (f"تم اعتماد المنتج {sku.strip()} ونشره في نتائج البحث." if approve
            else f"تم أرشفة المنتج {sku.strip()} بعد المراجعة.")
