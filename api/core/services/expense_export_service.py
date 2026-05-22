"""Per-expense export builders: PDF (receipt-style one-pager) + CSV (single row).

Attachments are listed by filename only — actual binary content is NOT
embedded. A future ZIP bundle endpoint will include attachment bytes.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from core.models.models_per_tenant import Expense, ExpenseAttachment

# CSV column order — stable for downstream tools.
CSV_COLUMNS = [
    "id",
    "expense_date",
    "vendor",
    "category",
    "amount",
    "currency",
    "tax_amount",
    "total_amount",
    "payment_method",
    "reference_number",
    "status",
    "labels",
    "notes",
    "attachment_count",
    "created_at",
    "updated_at",
]


def _fmt_date(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    return str(value)


def _fmt_dt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _labels_csv(labels) -> str:
    if not labels:
        return ""
    if not isinstance(labels, list):
        return str(labels)
    return ";".join(str(s) for s in labels)


def build_expense_csv_row(expense: Expense, attachment_count: int) -> bytes:
    """Return UTF-8 CSV bytes — header row + one data row."""
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(CSV_COLUMNS)
    writer.writerow(
        [
            expense.id,
            _fmt_date(expense.expense_date),
            expense.vendor or "",
            expense.category or "",
            f"{float(expense.amount or 0):.2f}",
            expense.currency or "",
            f"{float(expense.tax_amount):.2f}" if expense.tax_amount is not None else "",
            f"{float(expense.total_amount):.2f}" if expense.total_amount is not None else "",
            expense.payment_method or "",
            expense.reference_number or "",
            expense.status or "",
            _labels_csv(expense.labels),
            expense.notes or "",
            attachment_count,
            _fmt_dt(expense.created_at),
            _fmt_dt(expense.updated_at),
        ]
    )
    return buf.getvalue().encode("utf-8")


def _build_pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ExpTitle",
            parent=styles["Heading1"],
            fontSize=18,
            spaceAfter=12,
            alignment=TA_LEFT,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ExpSection",
            parent=styles["Heading3"],
            fontSize=11,
            spaceBefore=6,
            spaceAfter=4,
            alignment=TA_LEFT,
        )
    )
    return styles


def build_expense_pdf(expense: Expense, attachments: List[ExpenseAttachment]) -> bytes:
    """Render a one-page receipt-style PDF for a single expense."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.5 * inch,
        bottomMargin=0.5 * inch,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
    )
    styles = _build_pdf_styles()
    elements = []

    title = expense.vendor or "Expense"
    elements.append(Paragraph(f"{title} — Expense #{expense.id}", styles["ExpTitle"]))

    summary_rows = [
        ["Date", _fmt_date(expense.expense_date)],
        ["Amount", f"{float(expense.amount or 0):,.2f} {expense.currency or ''}"],
        ["Category", expense.category or "—"],
        ["Vendor", expense.vendor or "—"],
        ["Payment", expense.payment_method or "—"],
        ["Reference", expense.reference_number or "—"],
        ["Status", expense.status or "—"],
    ]
    if expense.tax_amount is not None:
        summary_rows.append(["Tax", f"{float(expense.tax_amount):,.2f}"])
    if expense.total_amount is not None:
        summary_rows.append(["Total", f"{float(expense.total_amount):,.2f}"])
    table = Table(summary_rows, colWidths=[1.5 * inch, 4.5 * inch])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)

    if expense.labels:
        labels = expense.labels if isinstance(expense.labels, list) else [str(expense.labels)]
        if labels:
            elements.append(Spacer(1, 0.15 * inch))
            elements.append(Paragraph("Labels", styles["ExpSection"]))
            elements.append(Paragraph(", ".join(str(l) for l in labels), styles["Normal"]))

    if expense.notes:
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("Notes", styles["ExpSection"]))
        # Render notes as a code-style monospace block so the raw markdown source
        # is preserved verbatim in the PDF (reportlab does not render markdown).
        # Downstream readers can copy/paste the source if needed.
        for line in (expense.notes or "").splitlines() or [""]:
            elements.append(Paragraph(line.replace(" ", "&nbsp;") or "&nbsp;", styles["Code"]))

    elements.append(Spacer(1, 0.2 * inch))
    elements.append(Paragraph("Attachments", styles["ExpSection"]))
    if attachments:
        rows = [["Filename", "Size (bytes)", "Type"]]
        for a in attachments:
            rows.append([a.filename or "—", str(a.file_size or ""), a.content_type or "—"])
        att_table = Table(rows, colWidths=[3.5 * inch, 1.3 * inch, 1.7 * inch])
        att_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ]
            )
        )
        elements.append(att_table)
        elements.append(Spacer(1, 0.1 * inch))
        elements.append(
            Paragraph(
                "<i>Attachment files are not embedded in this PDF. "
                "A ZIP-bundle export (PDF + JSON + attachment files) is planned.</i>",
                styles["Italic"],
            )
        )
    else:
        elements.append(Paragraph("<i>No attachments.</i>", styles["Italic"]))

    doc.build(elements)
    return buf.getvalue()
