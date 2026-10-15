"""Unit tests for extractor module (CSV, Excel, exceptions)."""

from pathlib import Path
import pandas as pd
import pytest

from src.extractor import extract_data


def test_extract_csv(tmp_path: Path) -> None:
    """Verifies reading data from CSV files."""
    csv_file = tmp_path / "test.csv"
    pd.DataFrame({"col_a": [1, 2], "col_b": ["x", "y"]}).to_csv(csv_file, index=False)

    df = extract_data(csv_file, base_dir=tmp_path)
    assert len(df) == 2
    assert list(df.columns) == ["col_a", "col_b"]


def test_extract_excel(tmp_path: Path) -> None:
    """Verifies reading data from Excel (.xlsx) files."""
    xlsx_file = tmp_path / "test.xlsx"
    pd.DataFrame({"revenue": [100.0, 250.0]}).to_excel(xlsx_file, index=False, engine="openpyxl")

    df = extract_data(xlsx_file, base_dir=tmp_path)
    assert len(df) == 2
    assert "revenue" in df.columns


def test_extract_non_existent_file() -> None:
    """Verifies FileNotFoundError on non-existent path."""
    with pytest.raises(FileNotFoundError):
        extract_data("non_existent_file.csv")


def test_extract_unsupported_format(tmp_path: Path) -> None:
    """Verifies ValueError when encountering unsupported extension."""
    txt_file = tmp_path / "file.txt"
    txt_file.write_text("hello", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported file format"):
        extract_data(txt_file, base_dir=tmp_path)


def test_extract_empty_file(tmp_path: Path) -> None:
    """Verifies handling of completely empty file."""
    empty_csv = tmp_path / "empty.csv"
    empty_csv.write_text("", encoding="utf-8")

    with pytest.raises(Exception):
        extract_data(empty_csv, base_dir=tmp_path)
