"""Unit tests for Pydantic schema validation and business rules."""

from datetime import date
import pytest
from pydantic import ValidationError

from src.schemas import TransactionRecord, AnomalyRecord


def test_valid_transaction_record() -> None:
    """Verifies that a well-formed transaction passes validation."""
    data = {
        "transaction_id": "TX-1001",
        "date": "2026-03-01",
        "region": "North",
        "category": "Technology",
        "customer_segment": "Enterprise",
        "units_sold": 10,
        "unit_price": 500.0,
        "discount_pct": 0.15,
        "shipping_cost": 50.0,
        "payment_status": "Completed"
    }
    record = TransactionRecord.model_validate(data)
    assert record.transaction_id == "TX-1001"
    assert record.date == date(2026, 3, 1)
    assert record.region == "North"
    assert record.units_sold == 10
    assert record.unit_price == 500.0
    assert record.discount_pct == 0.15


def test_schema_normalizes_case_and_dates() -> None:
    """Tests case normalization and multi-format date parsing."""
    data = {
        "transaction_id": "TX-1002",
        "date": "15/03/2026",
        "region": "  south  ",
        "category": "Furniture",
        "customer_segment": "SMB",
        "units_sold": 2,
        "unit_price": 100.0,
        "discount_pct": 0.05,
        "shipping_cost": 10.0,
        "payment_status": "  completed  "
    }
    record = TransactionRecord.model_validate(data)
    assert record.region == "South"
    assert record.payment_status == "Completed"
    assert record.date == date(2026, 3, 15)


def test_invalid_region_raises_validation_error() -> None:
    """Tests that unlisted regions are rejected."""
    data = {
        "transaction_id": "TX-1003",
        "date": "2026-03-01",
        "region": "Antarctica",
        "category": "Technology",
        "customer_segment": "Enterprise",
        "units_sold": 5,
        "unit_price": 100.0,
        "payment_status": "Completed"
    }
    with pytest.raises(ValidationError) as exc:
        TransactionRecord.model_validate(data)
    assert "Invalid region" in str(exc.value)


def test_excessive_discount_rejected() -> None:
    """Verifies that discounts above policy threshold are rejected."""
    data = {
        "transaction_id": "TX-1004",
        "date": "2026-03-01",
        "region": "West",
        "category": "Technology",
        "customer_segment": "Enterprise",
        "units_sold": 5,
        "unit_price": 100.0,
        "discount_pct": 0.85,  # Exceeds 70% threshold
        "payment_status": "Completed"
    }
    with pytest.raises(ValidationError) as exc:
        TransactionRecord.model_validate(data)
    assert "exceeds maximum allowable policy" in str(exc.value)


def test_negative_or_zero_units_sold_rejected() -> None:
    """Tests constraint gt=0 on units_sold."""
    data = {
        "transaction_id": "TX-1005",
        "date": "2026-03-01",
        "region": "West",
        "category": "Technology",
        "customer_segment": "Enterprise",
        "units_sold": 0,
        "unit_price": 100.0,
        "payment_status": "Completed"
    }
    with pytest.raises(ValidationError):
        TransactionRecord.model_validate(data)


def test_negative_unit_price_rejected() -> None:
    """Tests constraint gt=0 on unit_price."""
    data = {
        "transaction_id": "TX-1006",
        "date": "2026-03-01",
        "region": "West",
        "category": "Technology",
        "customer_segment": "Enterprise",
        "units_sold": 5,
        "unit_price": -20.0,
        "payment_status": "Completed"
    }
    with pytest.raises(ValidationError):
        TransactionRecord.model_validate(data)


def test_anomaly_record_structure() -> None:
    """Verifies AnomalyRecord dataclass serialization."""
    anom = AnomalyRecord(
        row_index=42,
        transaction_id="TX-ERR",
        field_name="discount_pct",
        error_message="Discount too high",
        raw_value="0.95"
    )
    assert anom.row_index == 42
    assert anom.field_name == "discount_pct"
