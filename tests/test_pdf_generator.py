"""Integration tests for PDF document generation and visual chart embedding."""

from pathlib import Path
import pandas as pd
import pytest

from src.transformer import transform_data
from src.visualizer import generate_all_charts
from src.pdf_generator import build_pdf_report


@pytest.fixture
def sample_dataset() -> pd.DataFrame:
    return pd.DataFrame([
        {"transaction_id": "TX-1", "date": "2026-03-01", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 10, "unit_price": 500.0, "discount_pct": 0.10, "shipping_cost": 20.0, "payment_status": "Completed"},
        {"transaction_id": "TX-2", "date": "2026-03-02", "region": "South", "category": "Furniture", "customer_segment": "SMB", "units_sold": 5, "unit_price": 200.0, "discount_pct": 0.05, "shipping_cost": 15.0, "payment_status": "Completed"},
        {"transaction_id": "TX-3", "date": "2026-03-03", "region": "West", "category": "Office Supplies", "customer_segment": "Consumer", "units_sold": 25, "unit_price": 40.0, "discount_pct": 0.00, "shipping_cost": 10.0, "payment_status": "Completed"},
        # 1 anomaly to test audit table in PDF
        {"transaction_id": "TX-BAD", "date": "2026-03-04", "region": "North", "category": "Technology", "customer_segment": "SMB", "units_sold": -5, "unit_price": 100.0, "discount_pct": 0.0, "shipping_cost": 10.0, "payment_status": "Completed"},
    ])


def test_build_pdf_report_generates_valid_file(sample_dataset: pd.DataFrame, tmp_path: Path) -> None:
    """Verifies that PDF builds cleanly into a non-empty binary file."""
    result = transform_data(sample_dataset)
    charts = generate_all_charts(result.valid_df)

    output_file = tmp_path / "test_report.pdf"
    generated_path = build_pdf_report(result, charts, output_path=output_file, base_dir=tmp_path)

    assert generated_path.is_file()
    assert generated_path.stat().st_size > 10_000  # PDF should be at least ~10KB with images

    # Check magic bytes for PDF
    with open(generated_path, "rb") as f:
        header = f.read(4)
        assert header == b"%PDF"


def test_pdf_report_without_anomalies(tmp_path: Path) -> None:
    """Tests PDF generation on 100% clean data with zero anomalies."""
    clean_df = pd.DataFrame([
        {"transaction_id": "TX-1", "date": "2026-03-01", "region": "East", "category": "Furniture", "customer_segment": "SMB", "units_sold": 8, "unit_price": 150.0, "discount_pct": 0.05, "shipping_cost": 25.0, "payment_status": "Completed"}
    ])
    result = transform_data(clean_df)
    charts = generate_all_charts(result.valid_df)

    output_file = tmp_path / "clean_report.pdf"
    generated = build_pdf_report(result, charts, output_path=output_file, base_dir=tmp_path)

    assert generated.is_file()
    assert generated.stat().st_size > 5_000
