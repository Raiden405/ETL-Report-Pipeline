"""Pydantic v2 schemas for data ingestion, validation, and anomaly tracking."""

import datetime as dt
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict

from src.config import MAX_ALLOWED_DISCOUNT, VALID_PAYMENT_STATUSES, VALID_REGIONS


class TransactionRecord(BaseModel):
    """Represents a validated, single business transaction record."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    transaction_id: str = Field(..., min_length=3, description="Unique transaction identifier")
    date: dt.date = Field(..., description="Date of the transaction")
    region: str = Field(..., min_length=2, description="Sales region")
    category: str = Field(..., min_length=2, description="Product merchandise category")
    customer_segment: str = Field(..., min_length=2, description="Customer segment classification")
    units_sold: int = Field(..., gt=0, description="Quantity of units sold, must be positive")
    unit_price: float = Field(..., gt=0.0, description="Price per unit in currency, must be positive")
    discount_pct: float = Field(0.0, ge=0.0, le=1.0, description="Discount rate between 0.0 and 1.0")
    shipping_cost: float = Field(0.0, ge=0.0, description="Freight/shipping cost")
    payment_status: str = Field(..., description="Status of payment lifecycle")

    @field_validator("region")
    @classmethod
    def validate_region(cls, v: str) -> str:
        clean = v.strip().title()
        if clean not in VALID_REGIONS:
            raise ValueError(f"Invalid region '{clean}'. Expected one of {sorted(VALID_REGIONS)}")
        return clean

    @field_validator("payment_status")
    @classmethod
    def validate_payment_status(cls, v: str) -> str:
        clean = v.strip().title()
        if clean not in VALID_PAYMENT_STATUSES:
            raise ValueError(f"Invalid payment status '{clean}'. Expected one of {sorted(VALID_PAYMENT_STATUSES)}")
        return clean

    @field_validator("discount_pct")
    @classmethod
    def validate_discount(cls, v: float) -> float:
        if v > MAX_ALLOWED_DISCOUNT:
            raise ValueError(
                f"Discount {v:.1%} exceeds maximum allowable policy of {MAX_ALLOWED_DISCOUNT:.1%}"
            )
        return round(float(v), 4)

    @field_validator("date", mode="before")
    @classmethod
    def parse_transaction_date(cls, v: Any) -> dt.date:
        if isinstance(v, dt.datetime):
            return v.date()
        if isinstance(v, dt.date):
            return v
        if isinstance(v, str):
            # Parse ISO or slash formats
            clean = v.strip()
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
                try:
                    return dt.datetime.strptime(clean, fmt).date()
                except ValueError:
                    continue
        raise ValueError(f"Cannot parse date from value '{v}'")

    @model_validator(mode="after")
    def validate_business_rules(self) -> "TransactionRecord":
        # Rule: Refunded transactions cannot have positive shipping cost charged
        if self.payment_status == "Cancelled" and self.units_sold > 500:
            raise ValueError("High-volume orders (>500 units) require manual executive cancellation audit")
        return self


class AnomalyRecord(BaseModel):
    """Structured record describing a rejected data row or schema inconsistency."""
    row_index: int
    transaction_id: Optional[str] = None
    field_name: str
    error_message: str
    raw_value: Optional[str] = None
