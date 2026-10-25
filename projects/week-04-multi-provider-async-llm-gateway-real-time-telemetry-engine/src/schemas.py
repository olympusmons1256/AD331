from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str = Field(..., min_length=1)
    quantity: int = Field(..., gt=0)
    unit_price: float = Field(..., gt=0)
    line_total: float = Field(..., gt=0)

    @field_validator("line_total")
    @classmethod
    def validate_line_total_matches_quantity_price(cls, value: float, info) -> float:
        quantity = info.data.get("quantity")
        unit_price = info.data.get("unit_price")
        if quantity is not None and unit_price is not None:
            expected = round(quantity * unit_price, 2)
            if abs(value - expected) > 0.02:
                raise ValueError("line_total must equal quantity * unit_price within 0.02 tolerance")
        return value


class InvoiceExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invoice_number: str = Field(..., min_length=3)
    vendor_name: str = Field(..., min_length=2)
    invoice_date: date
    line_items: list[LineItem] = Field(..., min_length=1)
    subtotal: float = Field(..., ge=0)
    tax_amount: float = Field(..., ge=0)
    total_amount: float = Field(..., ge=0)
    currency: Literal["USD", "EUR", "GBP"]

    @field_validator("invoice_number")
    @classmethod
    def validate_invoice_number(cls, value: str) -> str:
        cleaned = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9\-]+", cleaned):
            raise ValueError("invoice_number must be alphanumeric or hyphenated")
        return cleaned

    @field_validator("invoice_date", mode="before")
    @classmethod
    def normalize_invoice_date(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%b %d, %Y", "%d %B %Y", "%d %b %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue

        match = re.match(r"^(\d{1,2})(?:st|nd|rd|th)\s+of\s+([A-Za-z]+),\s*(\d{4})$", candidate, flags=re.IGNORECASE)
        if match:
            day, month_name, year = match.groups()
            return datetime.strptime(f"{day} {month_name} {year}", "%d %B %Y").date()
        raise ValueError("invoice_date must be a valid ISO-like date")

    @model_validator(mode="after")
    def validate_reconciliation(self) -> "InvoiceExtraction":
        line_total_sum = sum(item.line_total for item in self.line_items)
        if abs(line_total_sum - self.subtotal) > 0.02:
            raise ValueError("subtotal must equal the sum of all line item totals")
        if abs((line_total_sum + self.tax_amount) - self.total_amount) > 0.02:
            raise ValueError("total_amount must reconcile with item totals and tax")
        return self
