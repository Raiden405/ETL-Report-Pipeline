"""Security regression and vulnerability prevention test suite.

Simulates real-world attack vectors to verify that defensive controls
reject malicious inputs and adhere to AppSec standards (CWE-22, CWE-73,
CWE-79, CWE-116, CWE-377, CWE-400, CWE-409, CWE-532, CWE-1236).
"""

from pathlib import Path
import io
import logging
import zipfile
import pandas as pd
import pytest
from unittest.mock import patch

from src.config import (
    RAW_DIR,
    PROCESSED_DIR,
    MAX_FILE_SIZE_BYTES,
    MAX_ALLOWED_ROWS,
    validate_safe_path,
)
from src.extractor import extract_data, sanitize_formula_injection, validate_excel_safety
from src.transformer import transform_data
from src.visualizer import generate_all_charts
from src.pdf_generator import build_pdf_report
from src.logger import setup_logger, SensitiveDataRedactor
from main import run_pipeline


# ============================================================================
# 1. Path Traversal & Arbitrary File Manipulation (CWE-22 / CWE-73)
# ============================================================================

def test_path_traversal_relative_rejected(tmp_path: Path) -> None:
    """Verifies that relative path traversal payloads are blocked."""
    jail_dir = tmp_path / "jail"
    jail_dir.mkdir()

    # Attempting to escape jail_dir using ../
    traversal_path = "../../etc/passwd"
    with pytest.raises(PermissionError, match="outside permitted directory"):
        extract_data(traversal_path, base_dir=jail_dir)


def test_path_traversal_absolute_rejected(tmp_path: Path) -> None:
    """Verifies that absolute paths outside allowed base_dir are rejected."""
    jail_dir = tmp_path / "jail"
    jail_dir.mkdir()

    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("classified", encoding="utf-8")

    with pytest.raises(PermissionError, match="outside permitted directory"):
        extract_data(outside_file.resolve(), base_dir=jail_dir)


def test_pdf_output_path_traversal_rejected(tmp_path: Path) -> None:
    """Verifies that arbitrary output PDF writes outside PROCESSED_DIR are blocked."""
    fake_df = pd.DataFrame([
        {"transaction_id": "TX-1", "date": "2026-03-01", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 10, "unit_price": 100.0, "discount_pct": 0.1, "shipping_cost": 10.0, "payment_status": "Completed"}
    ])
    result = transform_data(fake_df)
    charts = generate_all_charts(result.valid_df)

    allowed_dir = tmp_path / "processed"
    allowed_dir.mkdir()

    malicious_output = "../../target_overwrite.pdf"
    with pytest.raises(PermissionError, match="outside permitted directory"):
        build_pdf_report(result, charts, output_path=malicious_output, base_dir=allowed_dir)


def test_main_pipeline_rejects_traversal() -> None:
    """Verifies that CLI orchestrator rejects traversal in input and output arguments."""
    with pytest.raises(PermissionError):
        run_pipeline(input_path=Path("../../outside.csv"))

    # When input is valid, test output path traversal
    valid_csv = RAW_DIR / "sample_sales.csv"
    if not valid_csv.is_file():
        pd.DataFrame([{"transaction_id": "TX-1", "date": "2026-03-01", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 10, "unit_price": 100.0, "discount_pct": 0.1, "shipping_cost": 10.0, "payment_status": "Completed"}]).to_csv(valid_csv, index=False)

    with pytest.raises(PermissionError):
        run_pipeline(input_path=valid_csv, output_path=Path("../../escape.pdf"))


# ============================================================================
# 2. CSV / Formula Injection (CWE-1236)
# ============================================================================

def test_formula_injection_sanitization_helper() -> None:
    """Unit test for formula injection sanitization logic."""
    assert sanitize_formula_injection("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_formula_injection("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_formula_injection("@HYPERLINK('http://evil.com')") == "'@HYPERLINK('http://evil.com')"
    assert sanitize_formula_injection("-cmd") == "'-cmd"
    assert sanitize_formula_injection("\t=1+1") == "'\t=1+1"
    # Valid numeric values should NOT be mangled
    assert sanitize_formula_injection("-50.0") == "-50.0"
    assert sanitize_formula_injection("+100") == "+100"
    assert sanitize_formula_injection("Normal Text") == "Normal Text"


def test_formula_injection_sanitization_in_csv(tmp_path: Path) -> None:
    """Verifies that CSV extraction sanitizes malicious formula triggers."""
    csv_file = tmp_path / "malicious_formulas.csv"
    df = pd.DataFrame({
        "transaction_id": ["=cmd|' /C calc'!A0", "+HYPERLINK('http://evil.com')", "TX-100"],
        "category": ["@SUM(1,2)", "Normal", "=2+5"],
        "price": [-45.5, 100.0, 20.0]
    })
    df.to_csv(csv_file, index=False)

    extracted = extract_data(csv_file, base_dir=tmp_path)

    # All formula triggers must be prepended with a single quote
    assert extracted.loc[0, "transaction_id"] == "'=cmd|' /C calc'!A0"
    assert extracted.loc[1, "transaction_id"] == "'+HYPERLINK('http://evil.com')"
    assert extracted.loc[2, "transaction_id"] == "TX-100"
    assert extracted.loc[0, "category"] == "'@SUM(1,2)"
    assert extracted.loc[2, "category"] == "'=2+5"
    # Negative number remains intact
    assert extracted.loc[0, "price"] == -45.5


def test_formula_injection_in_anomalies() -> None:
    """Verifies that rejected anomalies also sanitize formula characters in raw_value and TX ID."""
    mixed_df = pd.DataFrame([
        # Valid row to allow transform_data completion
        {
            "transaction_id": "TX-OK",
            "date": "2026-03-01",
            "region": "North",
            "category": "Technology",
            "customer_segment": "Enterprise",
            "units_sold": 10,
            "unit_price": 100.0,
            "discount_pct": 0.1,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        },
        # Anomaly with formula characters
        {
            "transaction_id": "=cmd|' /C calc'!A0",
            "date": "invalid-date",
            "region": "+MALICIOUS_REGION",
            "category": "@MALICIOUS_CAT",
            "customer_segment": "Enterprise",
            "units_sold": -5,
            "unit_price": 100.0,
            "discount_pct": 0.0,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        }
    ])
    result = transform_data(mixed_df)
    assert len(result.anomalies) > 0
    for anom in result.anomalies:
        assert str(anom.transaction_id).startswith("'=")


# ============================================================================
# 3. Content Injection and XSS in PDF Generation (CWE-79 / CWE-116)
# ============================================================================

def test_pdf_generation_escapes_html_and_xml_tags(tmp_path: Path) -> None:
    """Verifies that XML/HTML injection payloads in text fields do not cause ExpatError or SSRF."""
    xss_payloads = [
        "<script>alert('XSS')</script>",
        "<font color='red'><b>PWNED</b></font>",
        "AT&T & <UnclosedTag>",
        "<img src='http://169.254.169.254/latest/meta-data/'>",
    ]

    dirty_df = pd.DataFrame([
        {
            "transaction_id": xss_payloads[0],
            "date": "2026-03-01",
            "region": "North",
            "category": xss_payloads[1],
            "customer_segment": "Enterprise",
            "units_sold": 10,
            "unit_price": 100.0,
            "discount_pct": 0.1,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        },
        # Anomaly with XML payloads to test audit log table
        {
            "transaction_id": xss_payloads[2],
            "date": "invalid-date",
            "region": "South",
            "category": xss_payloads[3],
            "customer_segment": "SMB",
            "units_sold": 0,
            "unit_price": 50.0,
            "discount_pct": 0.0,
            "shipping_cost": 10.0,
            "payment_status": "Completed"
        }
    ])

    result = transform_data(dirty_df)
    charts = generate_all_charts(result.valid_df)

    output_pdf = tmp_path / "xss_test_report.pdf"
    # Should build cleanly without throwing xml.parsers.expat.ExpatError
    built_path = build_pdf_report(result, charts, output_path=output_pdf, base_dir=tmp_path)
    assert built_path.is_file()
    assert built_path.stat().st_size > 5_000


# ============================================================================
# 4. Resource Exhaustion & Denial of Service (CWE-400 / CWE-409)
# ============================================================================

def test_extract_rejects_oversized_file(tmp_path: Path) -> None:
    """Verifies that files exceeding MAX_FILE_SIZE_BYTES are rejected before loading."""
    oversized_file = tmp_path / "oversized.csv"
    oversized_file.write_text("a,b\n1,2\n3,4\n5,6\n7,8\n", encoding="utf-8")

    # Patch MAX_FILE_SIZE_BYTES to a small threshold for testing
    with patch("src.extractor.MAX_FILE_SIZE_BYTES", 10):
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            extract_data(oversized_file, base_dir=tmp_path)


def test_excel_zip_bomb_detection(tmp_path: Path) -> None:
    """Verifies that an Excel file with an abnormal compression ratio is rejected."""
    zip_bomb_path = tmp_path / "bomb.xlsx"

    # Create a zip with high compression ratio
    with zipfile.ZipFile(zip_bomb_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 5 MB of repetitive zeroes compresses into ~5 KB (ratio ~1000:1)
        large_payload = b"0" * (5 * 1024 * 1024)
        zf.writestr("xl/worksheets/sheet1.xml", large_payload)

    with pytest.raises(ValueError, match="Potential Excel Zip Bomb"):
        validate_excel_safety(zip_bomb_path)


def test_csv_row_count_limit(tmp_path: Path) -> None:
    """Verifies that CSVs with rows exceeding MAX_ALLOWED_ROWS are rejected during chunking."""
    large_csv = tmp_path / "large.csv"
    # Create small CSV but mock chunk iteration to exceed limit
    large_csv.write_text("col\n1\n", encoding="utf-8")

    with patch("pandas.read_csv") as mock_read:
        # Mock generator that yields chunks exceeding MAX_ALLOWED_ROWS
        mock_read.return_value = [
            pd.DataFrame({"col": range(60_000)}),
            pd.DataFrame({"col": range(60_000)}),
        ]
        with pytest.raises(ValueError, match="exceeds maximum allowed limit"):
            extract_data(large_csv, base_dir=tmp_path)


# ============================================================================
# 5. Sensitive Information Exposure in Logs (CWE-532)
# ============================================================================

def test_logger_redacts_sensitive_credit_card_and_credentials() -> None:
    """Verifies that SensitiveDataRedactor filter redacts PII and secrets."""
    redactor = SensitiveDataRedactor()

    # Credit card redaction
    rec1 = logging.LogRecord(
        name="test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="Customer payment card: 4532-1234-5678-9012 failed", args=(), exc_info=None
    )
    redactor.filter(rec1)
    assert "4532-1234-5678-9012" not in rec1.msg
    assert "[REDACTED_CARD]" in rec1.msg

    # SSN redaction
    rec2 = logging.LogRecord(
        name="test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="Tax ID 123-45-6789 verified", args=(), exc_info=None
    )
    redactor.filter(rec2)
    assert "123-45-6789" not in rec2.msg
    assert "[REDACTED_SSN]" in rec2.msg

    # Secret / API key redaction in args
    rec3 = logging.LogRecord(
        name="test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="Auth failed for token: %s", args=("api_key=sk_live_supersecret999",), exc_info=None
    )
    redactor.filter(rec3)
    assert "sk_live_supersecret999" not in rec3.args[0]
    assert "[REDACTED_SECRET]" in rec3.args[0]


# ============================================================================
# 6. Insecure Temporary File Handling & Cleanup (CWE-377)
# ============================================================================

def test_pdf_temporary_file_cleanup_on_failure(tmp_path: Path) -> None:
    """Verifies that an error during PDF compilation cleans up temporary files without leaving artifacts."""
    fake_df = pd.DataFrame([
        {"transaction_id": "TX-1", "date": "2026-03-01", "region": "North", "category": "Technology", "customer_segment": "Enterprise", "units_sold": 10, "unit_price": 100.0, "discount_pct": 0.1, "shipping_cost": 10.0, "payment_status": "Completed"}
    ])
    result = transform_data(fake_df)
    charts = generate_all_charts(result.valid_df)

    output_file = tmp_path / "failed_report.pdf"

    # Force an exception during document build
    with patch("reportlab.platypus.SimpleDocTemplate.build", side_effect=RuntimeError("Build crashed")):
        with pytest.raises(RuntimeError, match="Build crashed"):
            build_pdf_report(result, charts, output_path=output_file, base_dir=tmp_path)

    # Destination file must not exist
    assert not output_file.exists()
    # No dangling temporary files left in directory
    remaining_files = list(tmp_path.glob("report_tmp_*.pdf"))
    assert len(remaining_files) == 0
