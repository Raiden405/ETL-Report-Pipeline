"""Main CLI entrypoint and orchestrator for the ETL Report Pipeline."""

import argparse
import sys
from pathlib import Path
from typing import Optional
import pandas as pd

from src.config import RAW_DIR, PROCESSED_DIR, validate_safe_path
from src.logger import setup_logger
from src.extractor import extract_data
from src.transformer import transform_data
from src.visualizer import generate_all_charts
from src.pdf_generator import build_pdf_report


def generate_sample_datasets() -> Path:
    """Creates realistic sample raw datasets (both CSV and Excel) with valid and anomalous records."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RAW_DIR / "sample_sales.csv"
    xlsx_path = RAW_DIR / "sample_sales.xlsx"

    records = [
        # Valid corporate transactions
        {"transaction_id": "TX-1001", "date": "2026-03-01", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 45, "unit_price": 750.00, "discount_pct": 0.10, "shipping_cost": 120.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1002", "date": "2026-03-02", "region": "South", "category": "Furniture", "customer_segment": "SMB", "units_sold": 12, "unit_price": 320.00, "discount_pct": 0.05, "shipping_cost": 45.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1003", "date": "2026-03-03", "region": "East", "category": "Office Supplies", "customer_segment": "Consumer", "units_sold": 110, "unit_price": 24.50, "discount_pct": 0.00, "shipping_cost": 15.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1004", "date": "2026-03-04", "region": "West", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 28, "unit_price": 1200.00, "discount_pct": 0.15, "shipping_cost": 85.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1005", "date": "2026-03-05", "region": "Central", "category": "Furniture", "customer_segment": "Enterprise", "units_sold": 35, "unit_price": 450.00, "discount_pct": 0.20, "shipping_cost": 90.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1006", "date": "2026-03-06", "region": "North", "category": "Office Supplies", "customer_segment": "SMB", "units_sold": 80, "unit_price": 38.00, "discount_pct": 0.05, "shipping_cost": 22.00, "payment_status": "Pending"},
        {"transaction_id": "TX-1007", "date": "2026-03-07", "region": "West", "category": "Technology", "customer_segment": "Consumer", "units_sold": 14, "unit_price": 540.00, "discount_pct": 0.00, "shipping_cost": 30.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1008", "date": "2026-03-08", "region": "East", "category": "Furniture", "customer_segment": "SMB", "units_sold": 18, "unit_price": 290.00, "discount_pct": 0.12, "shipping_cost": 50.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1009", "date": "2026-03-09", "region": "South", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 50, "unit_price": 890.00, "discount_pct": 0.18, "shipping_cost": 140.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1010", "date": "2026-03-10", "region": "Central", "category": "Office Supplies", "customer_segment": "Enterprise", "units_sold": 200, "unit_price": 18.00, "discount_pct": 0.10, "shipping_cost": 40.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1011", "date": "2026-03-11", "region": "North", "category": "Furniture", "customer_segment": "Consumer", "units_sold": 8, "unit_price": 620.00, "discount_pct": 0.00, "shipping_cost": 65.00, "payment_status": "Completed"},
        {"transaction_id": "TX-1012", "date": "2026-03-12", "region": "West", "category": "Office Supplies", "customer_segment": "SMB", "units_sold": 95, "unit_price": 42.00, "discount_pct": 0.08, "shipping_cost": 28.00, "payment_status": "Completed"},

        # Intentional anomalies for data quality testing / audit demonstration
        {"transaction_id": "TX-9901", "date": "2026-03-13", "region": "InvalidRegion", "category": "Technology", "customer_segment": "SMB", "units_sold": 10, "unit_price": 400.00, "discount_pct": 0.10, "shipping_cost": 20.00, "payment_status": "Completed"},
        {"transaction_id": "TX-9902", "date": "2026-03-14", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 0, "unit_price": 500.00, "discount_pct": 0.10, "shipping_cost": 25.00, "payment_status": "Completed"},
        {"transaction_id": "TX-9903", "date": "2026-03-15", "region": "South", "category": "Furniture", "customer_segment": "Consumer", "units_sold": 5, "unit_price": 200.00, "discount_pct": 0.85, "shipping_cost": 15.00, "payment_status": "Completed"},
        {"transaction_id": "TX-9904", "date": "invalid-date", "region": "East", "category": "Office Supplies", "customer_segment": "SMB", "units_sold": 20, "unit_price": 30.00, "discount_pct": 0.00, "shipping_cost": 10.00, "payment_status": "Completed"},
        {"transaction_id": "TX-9905", "date": "2026-03-17", "region": "West", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 15, "unit_price": -50.00, "discount_pct": 0.05, "shipping_cost": 10.00, "payment_status": "Completed"},
    ]

    sample_df = pd.DataFrame(records)
    sample_df.to_csv(csv_path, index=False)
    sample_df.to_excel(xlsx_path, index=False, engine="openpyxl")
    return csv_path


def run_pipeline(input_path: Optional[Path] = None, output_path: Optional[Path] = None) -> Path:
    """Executes the full end-to-end ETL and Executive Reporting process."""
    logger = setup_logger("pipeline_orchestrator")
    logger.info("==================================================")
    logger.info("   ETL REPORT AUTOMATION PIPELINE INITIALIZED     ")
    logger.info("==================================================")

    # 1. Resolve source input file safely (CWE-22 / CWE-73)
    if input_path:
        source_file = validate_safe_path(input_path, base_dir=RAW_DIR, check_exists=True)
        logger.info("Using validated input file: %s", source_file.name)
    else:
        existing_raw = list(RAW_DIR.glob("*.csv")) + list(RAW_DIR.glob("*.xlsx"))
        if existing_raw:
            source_file = existing_raw[0]
            logger.info("Using existing raw input file: %s", source_file.name)
        else:
            logger.info("No raw input file specified or found. Generating sample sales dataset...")
            source_file = generate_sample_datasets()

    # Validate output path destination if provided
    safe_output_path = validate_safe_path(output_path, base_dir=PROCESSED_DIR) if output_path else None

    # 2. Extract
    df_raw = extract_data(source_file, base_dir=RAW_DIR)

    # 3. Transform & Validate
    result = transform_data(df_raw)

    # 4. Visualize
    charts = generate_all_charts(result.valid_df)

    # 5. Generate PDF
    pdf_path = build_pdf_report(result, charts, output_path=safe_output_path)

    # 6. Summary Output
    kpis = result.kpis
    print("\n" + "=" * 58)
    print("   * ETL EXECUTIVE PIPELINE EXECUTION SUMMARY *   ")
    print("=" * 58)
    print(f" Source File        : {source_file.name}")
    print(f" Total Input Rows   : {result.total_raw_rows}")
    print(f" Valid Rows Passed  : {result.valid_rows_count}")
    print(f" Anomalies Flagged  : {result.invalid_rows_count}")
    print(f" Data Quality Score : {result.data_quality_score}%")
    print("-" * 58)
    print(f" Total Net Revenue  : ${kpis['total_net_revenue']:,.2f}")
    print(f" Total Units Sold   : {kpis['total_units_sold']:,}")
    print(f" Avg Order Value    : ${kpis['average_order_value']:,.2f}")
    print(f" Top Category       : {kpis['top_category']}")
    print(f" Top Region         : {kpis['top_region']}")
    print("-" * 58)
    print(f" Output Report PDF  : {pdf_path.resolve()}")
    print("=" * 58 + "\n")

    logger.info("Pipeline completed successfully. Artifact: %s", pdf_path)
    return pdf_path


def main() -> None:
    """CLI argument parser and entrypoint."""
    parser = argparse.ArgumentParser(
        description="Automated ETL Pipeline with Executive PDF Reporting.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "-i", "--input",
        type=Path,
        help="Path to raw tabular input file (.csv or .xlsx)."
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Target destination path for generated executive PDF."
    )
    parser.add_argument(
        "--generate-sample",
        action="store_true",
        help="Generate realistic raw sample data files in data/raw/ and exit."
    )

    args = parser.parse_args()

    if args.generate_sample:
        created = generate_sample_datasets()
        print(f"Sample datasets generated in: {created.parent.resolve()}")
        sys.exit(0)

    try:
        run_pipeline(input_path=args.input, output_path=args.output)
    except Exception as exc:
        print(f"\n[FATAL PIPELINE ERROR]: {exc}\n", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
