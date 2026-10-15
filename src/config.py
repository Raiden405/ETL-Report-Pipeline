"""Centralized pipeline configuration, paths, and visual design tokens."""

from pathlib import Path
from dataclasses import dataclass
from typing import Union


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
LOG_FILE = BASE_DIR / "pipeline.log"

# Ensure runtime directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Palette:
    """Executive corporate color palette."""
    PRIMARY: str = "#1A365D"       # Deep Corporate Navy
    SECONDARY: str = "#2B6CB0"     # Slate Blue
    ACCENT: str = "#2C7A7B"        # Teal
    SUCCESS: str = "#2F855A"       # Forest Green
    WARNING: str = "#DD6B20"       # Dark Amber
    DANGER: str = "#C53030"        # Crimson Red
    DARK: str = "#2D3748"          # Charcoal Text
    LIGHT_BG: str = "#F7FAFC"      # Subtle Gray
    CARD_BG: str = "#EDF2F7"       # Card / Container Gray
    BORDER: str = "#E2E8F0"        # Subtle Border
    WHITE: str = "#FFFFFF"         # Pure White
    ZEBRA_EVEN: str = "#FFFFFF"
    ZEBRA_ODD: str = "#F8FAFC"


PALETTE = Palette()


# Security & Resource Limits (CWE-400 / CWE-409)
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024          # 25 MB max file size
MAX_EXCEL_UNCOMPRESSED_BYTES = 100 * 1024 * 1024 # 100 MB max uncompressed zip size
MAX_EXCEL_COMPRESSION_RATIO = 100.0              # Max compression ratio for zip bomb protection
MAX_ALLOWED_ROWS = 100_000                       # Max row limit per extraction


def validate_safe_path(
    path: Union[str, Path],
    base_dir: Path,
    check_exists: bool = False
) -> Path:
    """Ensures path stays strictly within base_dir to prevent path traversal (CWE-22 / CWE-73)."""
    base = base_dir.resolve()
    target = Path(path)
    resolved = (base / target).resolve() if not target.is_absolute() else target.resolve()
    try:
        resolved.relative_to(base)
    except ValueError:
        raise PermissionError(f"Access denied: Path '{path}' is outside permitted directory '{base}'")
    if check_exists and not resolved.is_file():
        raise FileNotFoundError(f"File not found: {resolved}")
    return resolved


# Business Validation Rules
MAX_ALLOWED_DISCOUNT = 0.70  # Max 70% discount permitted without executive waiver
VALID_PAYMENT_STATUSES = {"Completed", "Pending", "Cancelled", "Refunded"}
VALID_REGIONS = {"North", "South", "East", "West", "Central"}
