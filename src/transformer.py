"""Data transformation, Pydantic validation, enrichment, and KPI aggregation."""

from dataclasses import dataclass, field
from typing import Any, Dict, List
import pandas as pd
from pydantic import ValidationError

from src.schemas import TransactionRecord, AnomalyRecord
from src.extractor import sanitize_formula_injection
from src.logger import setup_logger

logger = setup_logger("transformer")


@dataclass
class TransformationResult:
    """Contains validated dataset, flagged anomalies, and computed executive metrics."""
    valid_df: pd.DataFrame
    anomalies: List[AnomalyRecord] = field(default_factory=list)
    kpis: Dict[str, Any] = field(default_factory=dict)
    total_raw_rows: int = 0
    valid_rows_count: int = 0
    invalid_rows_count: int = 0

    @property
    def data_quality_score(self) -> float:
        """Percentage of successfully validated records."""
        if self.total_raw_rows == 0:
            return 0.0
        return round((self.valid_rows_count / self.total_raw_rows) * 100, 2)


def transform_data(df: pd.DataFrame) -> TransformationResult:
    """Validates raw DataFrame rows, enriches valid data, and calculates executive KPIs."""
    if df.empty:
        logger.warning("Empty DataFrame passed to transformation")
        return TransformationResult(valid_df=pd.DataFrame())

    total_rows = len(df)
    valid_records: List[Dict[str, Any]] = []
    anomalies: List[AnomalyRecord] = []

    logger.info("Starting validation of %d raw rows...", total_rows)

    # Convert DataFrame rows to records for Pydantic schema validation
    raw_dict_rows = df.to_dict(orient="records")

    for idx, row in enumerate(raw_dict_rows, start=1):
        try:
            record = TransactionRecord.model_validate(row)
            valid_records.append(record.model_dump())
        except ValidationError as err:
            for error_detail in err.errors():
                loc = ".".join(str(l) for l in error_detail.get("loc", ["unknown"]))
                msg = error_detail.get("msg", "Validation error")
                raw_val = str(row.get(loc, "")) if loc in row else None
                sanitized_val = sanitize_formula_injection(raw_val) if raw_val is not None else None
                tx_id = sanitize_formula_injection(str(row.get("transaction_id", f"ROW_{idx}")))
                anomaly = AnomalyRecord(
                    row_index=idx,
                    transaction_id=tx_id,
                    field_name=loc,
                    error_message=msg,
                    raw_value=sanitized_val
                )
                anomalies.append(anomaly)
                log_val = (raw_val[:100] + "...") if raw_val and len(raw_val) > 100 else raw_val
                logger.warning(
                    "Data Anomaly at Row %d (TX: %s) on '%s': %s (Raw: '%s')",
                    idx, anomaly.transaction_id, loc, msg, log_val
                )
        except Exception as exc:
            tx_id = sanitize_formula_injection(str(row.get("transaction_id", f"ROW_{idx}")))
            anomaly = AnomalyRecord(
                row_index=idx,
                transaction_id=tx_id,
                field_name="general",
                error_message=str(exc)
            )
            anomalies.append(anomaly)
            logger.error("Unexpected error at Row %d: %s", idx, exc)

    if not valid_records:
        logger.error("All %d rows failed validation. Pipeline halted.", total_rows)
        raise ValueError("Transformation failed: 0 valid records found in dataset.")

    valid_df = pd.DataFrame(valid_records)

    # Enrichment calculations
    valid_df["gross_revenue"] = valid_df["units_sold"] * valid_df["unit_price"]
    valid_df["discount_amount"] = valid_df["gross_revenue"] * valid_df["discount_pct"]
    valid_df["net_revenue"] = valid_df["gross_revenue"] - valid_df["discount_amount"]
    valid_df["total_order_value"] = valid_df["net_revenue"] + valid_df["shipping_cost"]

    # Calculate Executive KPIs
    total_net_rev = float(valid_df["net_revenue"].sum())
    total_gross_rev = float(valid_df["gross_revenue"].sum())
    total_units = int(valid_df["units_sold"].sum())
    order_count = len(valid_df)
    avg_order_value = float(valid_df["net_revenue"].mean()) if order_count else 0.0
    avg_discount = float(valid_df["discount_pct"].mean()) if order_count else 0.0

    # Categorical Aggregations
    cat_summary = (
        valid_df.groupby("category", as_index=False)
        .agg(
            revenue=("net_revenue", "sum"),
            units=("units_sold", "sum"),
            orders=("transaction_id", "count")
        )
        .sort_values(by="revenue", ascending=False)
    )

    region_summary = (
        valid_df.groupby("region", as_index=False)
        .agg(
            revenue=("net_revenue", "sum"),
            orders=("transaction_id", "count")
        )
        .sort_values(by="revenue", ascending=False)
    )

    kpis: Dict[str, Any] = {
        "total_gross_revenue": total_gross_rev,
        "total_net_revenue": total_net_rev,
        "total_units_sold": total_units,
        "total_orders": order_count,
        "average_order_value": avg_order_value,
        "average_discount_pct": avg_discount,
        "category_summary": cat_summary.to_dict(orient="records"),
        "region_summary": region_summary.to_dict(orient="records"),
        "top_category": cat_summary.iloc[0]["category"] if not cat_summary.empty else "N/A",
        "top_region": region_summary.iloc[0]["region"] if not region_summary.empty else "N/A",
    }

    logger.info(
        "Transformation completed: %d valid rows, %d anomalies. Total Net Revenue: $%.2f",
        len(valid_df), len(anomalies), total_net_rev
    )

    return TransformationResult(
        valid_df=valid_df,
        anomalies=anomalies,
        kpis=kpis,
        total_raw_rows=total_rows,
        valid_rows_count=len(valid_df),
        invalid_rows_count=len(anomalies)
    )
