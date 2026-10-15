"""Typed product catalog values; persistence adapters are implemented separately."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ProductRecord:
    tenant_id: str
    sku: str
    title: str
    price: Decimal | None = None
    currency: str | None = None
    description: str | None = None
    availability: str = "unknown"
    status: str = "active"
    attributes: dict[str, Any] | None = None
    offer_starts_at: datetime | None = None
    offer_ends_at: datetime | None = None
    source_channel_id: str | None = None
    source_message_id: str | None = None

    def validate(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not self.sku.strip():
            raise ValueError("sku is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if (self.price is None) != (self.currency is None):
            raise ValueError("price and currency must either both be set or both be absent")
        if self.price is not None and self.price < 0:
            raise ValueError("price cannot be negative")
        if self.currency is not None and (
            len(self.currency) != 3 or not self.currency.isalpha() or not self.currency.isupper()
        ):
            raise ValueError("currency must be a three-letter uppercase ISO code")
        if self.status not in {"active", "draft", "needs_review", "archived"}:
            raise ValueError("unsupported product status")
        if self.availability not in {
            "in_stock", "out_of_stock", "preorder", "discontinued", "unknown"
        }:
            raise ValueError("unsupported availability")
        if self.offer_starts_at and self.offer_ends_at:
            if self.offer_ends_at <= self.offer_starts_at:
                raise ValueError("offer_ends_at must be after offer_starts_at")
