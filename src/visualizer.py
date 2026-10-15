"""Corporate chart generator using matplotlib/seaborn rendered to memory buffers."""

import io
from typing import Dict
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend for automated pipelines
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd

from src.config import PALETTE
from src.logger import setup_logger

logger = setup_logger("visualizer")


def _format_currency(val: float, _pos: float = 0) -> str:
    """Format tick labels into clean compact currency ($12k, $1.5M)."""
    if val >= 1_000_000:
        return f"${val * 1e-6:.1f}M"
    if val >= 1_000:
        return f"${val * 1e-3:.0f}k"
    return f"${val:.0f}"


def create_category_bar_chart(df: pd.DataFrame) -> io.BytesIO:
    """Generates a horizontal bar chart of net revenue by product category."""
    cat_df = df.groupby("category", as_index=False)["net_revenue"].sum()
    cat_df = cat_df.sort_values(by="net_revenue", ascending=True)

    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=250)
    fig.patch.set_facecolor(PALETTE.WHITE)
    ax.set_facecolor(PALETTE.LIGHT_BG)

    bars = ax.barh(
        cat_df["category"],
        cat_df["net_revenue"],
        color=PALETTE.PRIMARY,
        edgecolor=PALETTE.SECONDARY,
        height=0.55,
        alpha=0.9
    )

    # Clean axes and borders
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(PALETTE.BORDER)
    ax.spines["bottom"].set_color(PALETTE.BORDER)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(_format_currency))
    ax.grid(axis="x", linestyle="--", alpha=0.3, color=PALETTE.DARK)

    # Bar value labels with padding to avoid overlap
    max_val = cat_df["net_revenue"].max() if not cat_df.empty else 1.0
    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            _format_currency(width),
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(6, 0),
            textcoords="offset points",
            ha="left",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color=PALETTE.DARK
        )

    ax.set_xlim(0, max_val * 1.22)
    ax.set_title("Net Revenue by Category", fontsize=11, fontweight="bold", color=PALETTE.PRIMARY, pad=12)
    ax.tick_params(colors=PALETTE.DARK, labelsize=9)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def create_trend_line_chart(df: pd.DataFrame) -> io.BytesIO:
    """Generates a clean timeline chart showing cumulative or periodic revenue."""
    trend_df = df.copy()
    trend_df["date"] = pd.to_datetime(trend_df["date"])
    # Aggregate by date
    daily = trend_df.groupby("date", as_index=False)["net_revenue"].sum().sort_values("date")

    fig, ax = plt.subplots(figsize=(6.5, 3.2), dpi=250)
    fig.patch.set_facecolor(PALETTE.WHITE)
    ax.set_facecolor(PALETTE.LIGHT_BG)

    ax.plot(
        daily["date"],
        daily["net_revenue"],
        color=PALETTE.SECONDARY,
        marker="o",
        markersize=4,
        linewidth=2.2,
        label="Revenue"
    )
    ax.fill_between(daily["date"], daily["net_revenue"], color=PALETTE.SECONDARY, alpha=0.12)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(PALETTE.BORDER)
    ax.spines["bottom"].set_color(PALETTE.BORDER)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(_format_currency))
    ax.grid(axis="y", linestyle="--", alpha=0.3, color=PALETTE.DARK)

    # Date format formatting on x-axis
    fig.autofmt_xdate(rotation=25)
    ax.set_title("Revenue Trajectory Over Time", fontsize=11, fontweight="bold", color=PALETTE.PRIMARY, pad=12)
    ax.tick_params(colors=PALETTE.DARK, labelsize=8.5)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def create_regional_donut_chart(df: pd.DataFrame) -> io.BytesIO:
    """Generates an executive donut chart showing revenue contribution per region."""
    reg_df = df.groupby("region", as_index=False)["net_revenue"].sum()
    reg_df = reg_df.sort_values(by="net_revenue", ascending=False)

    colors = [PALETTE.PRIMARY, PALETTE.SECONDARY, PALETTE.ACCENT, PALETTE.WARNING, "#4A5568"][:len(reg_df)]

    fig, ax = plt.subplots(figsize=(4.5, 3.2), dpi=250)
    fig.patch.set_facecolor(PALETTE.WHITE)

    wedges, texts, autotexts = ax.pie(
        reg_df["net_revenue"],
        labels=reg_df["region"],
        autopct="%1.1f%%",
        startangle=130,
        pctdistance=0.75,
        colors=colors,
        textprops={"color": PALETTE.DARK, "fontsize": 8.5},
        wedgeprops={"width": 0.45, "edgecolor": PALETTE.WHITE, "linewidth": 2}
    )

    for at in autotexts:
        at.set_fontsize(8)
        at.set_weight("bold")
        at.set_color(PALETTE.WHITE)

    ax.set_title("Regional Distribution", fontsize=11, fontweight="bold", color=PALETTE.PRIMARY, pad=12)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=250, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf


def generate_all_charts(df: pd.DataFrame) -> Dict[str, io.BytesIO]:
    """Coordinates generation of all executive visualization buffers."""
    logger.info("Rendering executive chart visualizations...")
    charts = {
        "category_bar": create_category_bar_chart(df),
        "trend_line": create_trend_line_chart(df),
        "regional_donut": create_regional_donut_chart(df),
    }
    logger.info("Successfully generated %d charts in memory.", len(charts))
    return charts
