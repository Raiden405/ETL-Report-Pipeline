"""Unit tests for data transformation, anomaly segregation, and KPI calculations."""

import pytest
import pandas as pd

from src.transformer import transform_data, TransformationResult


@pytest.fixture
def sample_valid_df() -> pd.DataFrame:
    """Fixture providing clean valid transactions."""
    return pd.DataFrame([
        {
            "transaction_id": "TX-101",
            "date": "2026-03-01",
            "region": "North",
            "category": "Technology",
            "customer_segment": "Enterprise",
            "units_sold": 10,
            "unit_price": 100.0,
            "discount_pct": 0.10,
            "shipping_cost": 20.0,
            "payment_status": "Completed"
        },
        {
            "transaction_id": "TX-102",
            "date": "2026-03-02",
            "region": "South",
            "category": "Furniture",
            "customer_segment": "SMB",
            "units_sold": 5,
            "unit_price": 200.0,
            "discount_pct": 0.20,
            "shipping_cost": 15.0,
            "payment_status": "Completed"
        }
    ])


@pytest.fixture
def sample_mixed_df() -> pd.DataFrame:
    """Fixture with valid transactions and intentional anomalies."""
    return pd.DataFrame([
        {
            "transaction_id": "TX-201",
            "date": "2026-03-01",
            "region": "North",
            "category": "Technology",
            "customer_segment": "Enterprise",
            "units_sold": 2,
            "unit_price": 500.0,
            "discount_pct": 0.10,
            "shipping_cost": 20.0,
            "payment_status": "Completed"
        },
        {
            # Anomaly: Negative units
            "transaction_id": "TX-BAD-1",
            "date": "2026-03-02",
            "region": "North",
            "category": "Technology",
            "customer_segment": "Enterprise",
            "units_sold": -5,
            "unit_price": 100.0,
            "discount_pct": 0.05,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        },
        {
            # Anomaly: Illegal discount > 0.70
            "transaction_id": "TX-BAD-2",
            "date": "2026-03-03",
            "region": "West",
            "category": "Furniture",
            "customer_segment": "SMB",
            "units_sold": 4,
            "unit_price": 100.0,
            "discount_pct": 0.95,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        }
    ])


def test_transform_valid_dataset(sample_valid_df: pd.DataFrame) -> None:
    """Tests successful calculations of financial metrics and KPIs."""
    res: TransformationResult = transform_data(sample_valid_df)

    assert res.total_raw_rows == 2
    assert res.valid_rows_count == 2
    assert res.invalid_rows_count == 0
    assert res.data_quality_score == 100.0
    assert len(res.anomalies) == 0

    # TX-101: 10 * 100 = 1000 gross. 10% disc = 100. Net = 900.
    # TX-102: 5 * 200 = 1000 gross. 20% disc = 200. Net = 800.
    # Total net: 900 + 800 = 1700
    assert res.kpis["total_gross_revenue"] == 2000.0
    assert res.kpis["total_net_revenue"] == 1700.0
    assert res.kpis["total_units_sold"] == 15
    assert res.kpis["average_order_value"] == 850.0


def test_transform_mixed_dataset_filters_anomalies(sample_mixed_df: pd.DataFrame) -> None:
    """Verifies that invalid rows are isolated without halting valid processing."""
    res = transform_data(sample_mixed_df)

    assert res.total_raw_rows == 3
    assert res.valid_rows_count == 1
    assert res.invalid_rows_count == 2
    assert len(res.anomalies) == 2
    assert res.data_quality_score == pytest.approx(33.33, rel=1e-2)

    flagged_fields = [a.field_name for a in res.anomalies]
    assert "units_sold" in flagged_fields
    assert "discount_pct" in flagged_fields


def test_all_invalid_rows_raises_value_error() -> None:
    """Verifies that 100% invalid dataset raises ValueError."""
    bad_df = pd.DataFrame([
        {"transaction_id": "TX-1", "date": "invalid", "region": "Invalid", "category": "Tech", "customer_segment": "SMB", "units_sold": -1, "unit_price": -5, "discount_pct": 2.0, "shipping_cost": 0, "payment_status": "Invalid"}
    ])
    with pytest.raises(ValueError, match="0 valid records"):
        transform_data(bad_df)


def test_empty_dataframe_handling() -> None:
    """Verifies handling of completely empty input DataFrame."""
    res = transform_data(pd.DataFrame())
    assert res.valid_df.empty
    assert res.total_raw_rows == 0
