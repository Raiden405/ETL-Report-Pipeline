"""Data extraction module for tabular raw inputs (CSV, Excel) with security validations."""

from pathlib import Path
from typing import Union, Any, Optional
import zipfile
import pandas as pd

from src.config import (
    RAW_DIR,
    MAX_FILE_SIZE_BYTES,
    MAX_EXCEL_UNCOMPRESSED_BYTES,
    MAX_EXCEL_COMPRESSION_RATIO,
    MAX_ALLOWED_ROWS,
    validate_safe_path,
)
from src.logger import setup_logger

logger = setup_logger("extractor")


def sanitize_formula_injection(val: Any) -> Any:
    """Neutralizes formula injection characters (=, +, -, @, \\t, \\r) for spreadsheet safety (CWE-1236)."""
    if isinstance(val, str):
        stripped = val.lstrip()
        if stripped and stripped[0] in ("=", "+", "-", "@", "\t", "\r"):
            try:
                float(stripped)
                return val
            except ValueError:
                return "'" + val
    return val


def validate_excel_safety(path: Path) -> None:
    """Inspects Excel (.xlsx) container to prevent Zip Bombs and resource exhaustion (CWE-400 / CWE-409)."""
    if not zipfile.is_zipfile(path):
        return
    with zipfile.ZipFile(path, "r") as zf:
        total_uncompressed = 0
        for info in zf.infolist():
            total_uncompressed += info.file_size
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_EXCEL_COMPRESSION_RATIO and info.file_size > 1024 * 1024:
                    raise ValueError(
                        f"Potential Excel Zip Bomb: compression ratio {ratio:.1f}:1 exceeds safety threshold of {MAX_EXCEL_COMPRESSION_RATIO}:1"
                    )
        if total_uncompressed > MAX_EXCEL_UNCOMPRESSED_BYTES:
            raise ValueError(
                f"Excel uncompressed content ({total_uncompressed / (1024*1024):.2f} MB) exceeds maximum allowed limit ({MAX_EXCEL_UNCOMPRESSED_BYTES / (1024*1024):.2f} MB)"
            )


def _read_csv_safely(path: Path) -> pd.DataFrame:
    """Reads CSV in bounded chunks to prevent memory exhaustion DoS (CWE-400)."""
    encodings = ("utf-8", "latin-1")
    for enc in encodings:
        try:
            chunks = []
            total_rows = 0
            for chunk in pd.read_csv(path, encoding=enc, chunksize=10_000):
                total_rows += len(chunk)
                if total_rows > MAX_ALLOWED_ROWS:
                    raise ValueError(
                        f"CSV dataset exceeds maximum allowed limit of {MAX_ALLOWED_ROWS:,} rows"
                    )
                chunks.append(chunk)
            return pd.concat(chunks, ignore_index=True) if chunks else pd.DataFrame()
        except UnicodeDecodeError:
            if enc == encodings[-1]:
                raise
            logger.warning("UTF-8 decoding failed for %s, falling back to latin-1", path.name)
    return pd.DataFrame()


def extract_data(file_path: Union[str, Path], base_dir: Path = RAW_DIR) -> pd.DataFrame:
    """Reads raw data from CSV/Excel with path validation, DoS mitigation, and formula sanitization.

    Raises:
        PermissionError: If path traverses outside allowed directory (CWE-22 / CWE-73).
        FileNotFoundError: If input file does not exist.
        ValueError: If file exceeds size limits (CWE-400), is unsupported, or empty.
    """
    path = validate_safe_path(file_path, base_dir=base_dir, check_exists=True)

    file_size = path.stat().st_size
    if file_size > MAX_FILE_SIZE_BYTES:
        raise ValueError(
            f"File size ({file_size / (1024*1024):.2f} MB) exceeds maximum allowed limit ({MAX_FILE_SIZE_BYTES / (1024*1024):.2f} MB)"
        )

    suffix = path.suffix.lower()
    logger.info("Extracting data from '%s' (%s)", path.name, suffix)

    try:
        if suffix == ".csv":
            df = _read_csv_safely(path)
        elif suffix in (".xlsx", ".xls"):
            if suffix == ".xlsx":
                validate_excel_safety(path)
            df = pd.read_excel(path, engine="openpyxl" if suffix == ".xlsx" else None)
            if len(df) > MAX_ALLOWED_ROWS:
                raise ValueError(f"Excel dataset exceeds maximum allowed limit of {MAX_ALLOWED_ROWS:,} rows")
        else:
            raise ValueError(f"Unsupported file format '{suffix}'. Supported: .csv, .xlsx, .xls")

    except Exception as exc:
        logger.error("Failed to parse file '%s': %s", path.name, exc)
        raise

    if df.empty:
        logger.warning("Extracted DataFrame is completely empty from: %s", path.name)
        raise ValueError(f"Extracted dataset is empty: {path.name}")

    # Neutralize potential Formula Injections in text columns (CWE-1236)
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].apply(sanitize_formula_injection)

    logger.info("Extraction successful: %d rows, %d columns loaded from %s", len(df), len(df.columns), path.name)
    return df
