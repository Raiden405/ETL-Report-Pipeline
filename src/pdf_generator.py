"""Executive PDF Report generation using ReportLab Platypus and modern typography."""

from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Union
import html
import io
import os
import tempfile

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    KeepTogether,
    HRFlowable,
)

from src.config import PALETTE, PROCESSED_DIR, validate_safe_path
from src.transformer import TransformationResult
from src.logger import setup_logger

logger = setup_logger("pdf_generator")


def _safe_text(val: Any) -> str:
    """Escapes XML/HTML special characters to prevent PDF injection / XSS (CWE-79 / CWE-116)."""
    if val is None:
        return "-"
    return html.escape(str(val), quote=True)


class NumberedCanvas(canvas.Canvas):
    """Canvas that enables two-pass total page count rendering and uniform footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_footer(num_pages)
            super().showPage()
        super().save()

    def _draw_footer(self, total_pages: int) -> None:
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor(PALETTE.DARK))
        self.setStrokeColor(colors.HexColor(PALETTE.BORDER))
        self.setLineWidth(0.6)
        # 40pt margin line
        self.line(40, 35, 555, 35)
        self.drawString(40, 22, "ETL Automation Engine  |  Confidential Executive Report")
        self.drawRightString(555, 22, f"Page {self._pageNumber} of {total_pages}")
        self.restoreState()


def _format_curr(value: float) -> str:
    return f"${value:,.2f}"


def build_pdf_report(
    result: TransformationResult,
    chart_buffers: Dict[str, io.BytesIO],
    output_path: Union[str, Path] = None,
    base_dir: Path = PROCESSED_DIR
) -> Path:
    """Compiles executive intelligence PDF with path validation, XSS escaping, and safe temp files."""
    if output_path:
        target_path = validate_safe_path(output_path, base_dir=base_dir)
    else:
        target_path = base_dir / f"executive_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

    target_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Building Executive PDF report: %s", target_path.name)

    content_width = A4[0] - 80  # 515.27 pt usable width

    styles = getSampleStyleSheet()

    # Typography styles
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor(PALETTE.PRIMARY)
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#718096")
    )
    section_h1 = ParagraphStyle(
        "SectionH1",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor(PALETTE.PRIMARY),
        spaceBefore=10,
        spaceAfter=6
    )
    card_value_style = ParagraphStyle(
        "CardValue",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=16,
        alignment=1,  # Center
        textColor=colors.HexColor(PALETTE.PRIMARY)
    )
    card_label_style = ParagraphStyle(
        "CardLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=1,  # Center
        textColor=colors.HexColor("#4A5568")
    )
    tbl_header_style = ParagraphStyle(
        "TblH",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=10,
        textColor=colors.white
    )
    tbl_cell_style = ParagraphStyle(
        "TblC",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(PALETTE.DARK)
    )
    tbl_cell_bold = ParagraphStyle(
        "TblCBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        textColor=colors.HexColor(PALETTE.DARK)
    )

    story: List[Any] = []

    # 1. Header Block with status badge
    badge_color = PALETTE.SUCCESS if result.data_quality_score >= 90.0 else PALETTE.WARNING
    badge_text = f"<font color='{badge_color}'>● QUALITY SCORE: {result.data_quality_score}%</font>"
    header_data = [
        [
            Paragraph("EXECUTIVE PERFORMANCE & ETL AUDIT", title_style),
            Paragraph(badge_text, ParagraphStyle("Badge", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, alignment=2))
        ],
        [
            Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y - %H:%M:%S')} | Automated Data Pipeline", subtitle_style),
            Paragraph("VERIFIED AUDIT", ParagraphStyle("SubBadge", parent=styles["Normal"], fontName="Helvetica", fontSize=8, alignment=2, textColor=colors.HexColor("#718096")))
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 155])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor(PALETTE.PRIMARY), spaceBefore=2, spaceAfter=10))

    # 2. Executive KPI Cards
    kpis = result.kpis
    col_w = content_width / 4.0
    cards_data = [
        [
            [Paragraph(_format_curr(kpis.get("total_net_revenue", 0.0)), card_value_style), Spacer(1, 2), Paragraph("NET REVENUE", card_label_style)],
            [Paragraph(f"{kpis.get('total_units_sold', 0):,}", card_value_style), Spacer(1, 2), Paragraph("UNITS SOLD", card_label_style)],
            [Paragraph(_format_curr(kpis.get("average_order_value", 0.0)), card_value_style), Spacer(1, 2), Paragraph("AVG ORDER VALUE", card_label_style)],
            [Paragraph(f"{result.valid_rows_count} / {result.total_raw_rows}", card_value_style), Spacer(1, 2), Paragraph("VALIDATED RECORDS", card_label_style)],
        ]
    ]
    cards_table = Table(cards_data, colWidths=[col_w] * 4)
    cards_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PALETTE.CARD_BG)),
        ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor(PALETTE.BORDER)),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor(PALETTE.BORDER)),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(cards_table)
    story.append(Spacer(1, 10))

    # 3. Visual Charts (Row 1: Category Bar & Regional Donut; Row 2: Trend Line)
    story.append(Paragraph("Strategic Visual Insights", section_h1))
    
    img_cat = Image(chart_buffers["category_bar"], width=290, height=135)
    img_reg = Image(chart_buffers["regional_donut"], width=215, height=135)
    chart_row1 = Table([[img_cat, img_reg]], colWidths=[295, 220])
    chart_row1.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(chart_row1)
    story.append(Spacer(1, 6))

    img_trend = Image(chart_buffers["trend_line"], width=content_width, height=130)
    story.append(img_trend)
    story.append(Spacer(1, 10))

    # 4. Financial & Category Breakdown (Zebra Table)
    story.append(Paragraph("Category Performance Matrix", section_h1))
    cat_records = kpis.get("category_summary", [])
    total_net = kpis.get("total_net_revenue", 1.0) or 1.0

    tbl_rows = [[
        Paragraph("Category", tbl_header_style),
        Paragraph("Units Sold", tbl_header_style),
        Paragraph("Net Revenue", tbl_header_style),
        Paragraph("Share (%)", tbl_header_style),
        Paragraph("Avg Price / Unit", tbl_header_style),
    ]]

    for item in cat_records:
        rev = item["revenue"]
        units = item["units"]
        share = (rev / total_net) * 100
        avg_price = rev / units if units else 0.0
        tbl_rows.append([
            Paragraph(_safe_text(item["category"]), tbl_cell_bold),
            Paragraph(f"{units:,}", tbl_cell_style),
            Paragraph(_format_curr(rev), tbl_cell_style),
            Paragraph(f"{share:.1f}%", tbl_cell_style),
            Paragraph(_format_curr(avg_price), tbl_cell_style),
        ])

    col_widths = [140, 85, 105, 85, 100]
    cat_table = Table(tbl_rows, colWidths=col_widths)
    t_style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PALETTE.PRIMARY)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(PALETTE.BORDER)),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    # Zebra styling
    for i in range(1, len(tbl_rows)):
        bg = colors.HexColor(PALETTE.ZEBRA_EVEN) if i % 2 == 0 else colors.HexColor(PALETTE.ZEBRA_ODD)
        t_style.append(("BACKGROUND", (0, i), (-1, i), bg))

    cat_table.setStyle(TableStyle(t_style))
    story.append(cat_table)
    story.append(Spacer(1, 10))

    # 5. Data Pipeline Quality & Anomaly Audit Log
    story.append(KeepTogether([
        Paragraph("Data Quality & Governance Audit", section_h1),
        Paragraph(
            f"<b>Batch Diagnostics:</b> Processed {result.total_raw_rows} input rows. "
            f"Accepted: <font color='{PALETTE.SUCCESS}'><b>{result.valid_rows_count}</b></font> | "
            f"Rejected / Anomalies: <font color='{PALETTE.DANGER}'><b>{len(result.anomalies)}</b></font>",
            subtitle_style
        ),
        Spacer(1, 4)
    ]))

    if result.anomalies:
        anomaly_rows = [[
            Paragraph("Row", tbl_header_style),
            Paragraph("Transaction ID", tbl_header_style),
            Paragraph("Field", tbl_header_style),
            Paragraph("Audit Issue", tbl_header_style),
            Paragraph("Raw Value", tbl_header_style),
        ]]
        # shortcut: cap display at top 8 anomalies in PDF to prevent page clutter; full list is in pipeline.log
        for anom in result.anomalies[:8]:
            anomaly_rows.append([
                Paragraph(str(anom.row_index), tbl_cell_style),
                Paragraph(_safe_text(anom.transaction_id), tbl_cell_bold),
                Paragraph(_safe_text(anom.field_name), tbl_cell_style),
                Paragraph(_safe_text(anom.error_message), tbl_cell_style),
                Paragraph(_safe_text(anom.raw_value), tbl_cell_style),
            ])

        anom_table = Table(anomaly_rows, colWidths=[40, 95, 90, 200, 90])
        anom_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PALETTE.DANGER)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(PALETTE.BORDER)),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i in range(1, len(anomaly_rows)):
            bg = colors.HexColor("#FFF5F5") if i % 2 == 1 else colors.white
            anom_style.append(("BACKGROUND", (0, i), (-1, i), bg))
        anom_table.setStyle(TableStyle(anom_style))
        story.append(anom_table)
    else:
        clean_box = Table(
            [[Paragraph("<font color='#276749'><b>✓ Zero Data Inconsistencies:</b> All incoming records strictly met schema and business policies.</font>", tbl_cell_style)]],
            colWidths=[content_width]
        )
        clean_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F0FFF4")),
            ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#9AE6B4")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(clean_box)

    # Build PDF with NumberedCanvas via secure temporary file to prevent race conditions & partial files (CWE-377)
    with tempfile.NamedTemporaryFile(
        prefix="report_tmp_",
        suffix=".pdf",
        dir=target_path.parent,
        delete=False
    ) as tmp_file:
        tmp_path = Path(tmp_file.name)

    try:
        doc = SimpleDocTemplate(
            str(tmp_path),
            pagesize=A4,
            leftMargin=40,
            rightMargin=40,
            topMargin=40,
            bottomMargin=45
        )
        doc.build(story, canvasmaker=NumberedCanvas)
        os.replace(tmp_path, target_path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

    logger.info("PDF generation completed successfully: %s", target_path.name)
    return target_path
