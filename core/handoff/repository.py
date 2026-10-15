"""PostgreSQL-backed conversation mode changes with tenant isolation and audit records."""
from __future__ import annotations
import os
from uuid import UUID
import psycopg

def set_conversation_mode(conversation_id: str, tenant_id: str, telegram_user_id: int, mode: str) -> str:
    if mode not in ("ai", "human"):
        return "وضع التحكم غير صالح."
    try:
        UUID(conversation_id)
        UUID(tenant_id)
    except (ValueError, TypeError):
        return "معرّف المحادثة غير صالح."
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET control_mode=%s, updated_at=now() WHERE id=%s::uuid AND tenant_id=%s::uuid RETURNING id::text",
                (mode, conversation_id, tenant_id),
            )
            row = cur.fetchone()
            result = "success" if row else "failed"
            cur.execute(
                "INSERT INTO operator_audit_log (tenant_id, telegram_user_id, action, target_type, target_id, result) VALUES (%s::uuid, %s, %s, 'conversation', %s, %s)",
                (tenant_id, str(telegram_user_id), "set_mode_" + mode, conversation_id, result),
            )
    if not row:
        return "لم تُعثر على المحادثة ضمن هذا المتجر."
    return "تم تحويل المحادثة إلى " + ("موظف." if mode == "human" else "الذكاء الاصطناعي.")

def get_conversation_status(conversation_id: str, tenant_id: str) -> str:
    try:
        UUID(conversation_id)
        UUID(tenant_id)
    except (ValueError, TypeError):
        return "معرّف المحادثة غير صالح."
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return "قاعدة البيانات غير مهيأة."
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT control_mode, status, last_message_at FROM conversations WHERE id=%s::uuid AND tenant_id=%s::uuid",
                (conversation_id, tenant_id),
            )
            row = cur.fetchone()
    if not row:
        return "لم تُعثر على المحادثة ضمن هذا المتجر."
    mode, status, last_message_at = row
    owner = "موظف" if mode == "human" else "الذكاء الاصطناعي"
    return f"الحالة: {status}\nالتحكم: {owner}\nآخر رسالة: {last_message_at or 'لا توجد'}"
