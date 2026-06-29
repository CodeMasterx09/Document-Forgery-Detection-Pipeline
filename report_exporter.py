# report_exporter.py
# Generates a professional downloadable PDF forensic audit report
# Enhanced with QR Code verification for document hash
# Called by app.py after analysis is complete

import io
import os
from datetime import datetime
from PIL import Image as PILImage

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak, Image as RLImage, KeepTogether
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

# QR Code generation
import qrcode


# ─────────────────────────────────────────────
#  COLOR PALETTE
# ─────────────────────────────────────────────
RED    = colors.HexColor("#dc3545")
ORANGE = colors.HexColor("#fd7e14")
GREEN  = colors.HexColor("#28a745")
BLUE   = colors.HexColor("#1e3c72")
LIGHT  = colors.HexColor("#f8f9fa")
GRAY   = colors.HexColor("#6c757d")
WHITE  = colors.white
BLACK  = colors.black
DARK   = colors.HexColor("#343a40")
CYAN   = colors.HexColor("#17a2b8")


# ─────────────────────────────────────────────
#  VERDICT COLOR HELPER
# ─────────────────────────────────────────────
def verdict_color(verdict):
    v = str(verdict).upper()
    if v in ["GENUINE", "AUTHENTIC"]:
        return GREEN
    elif v in ["SUSPICIOUS", "POSSIBLY_FORGED"]:
        return ORANGE
    return RED


# ─────────────────────────────────────────────
#  STYLES
# ─────────────────────────────────────────────
def get_styles():
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "ReportTitle", fontSize=20, textColor=WHITE,
            fontName="Helvetica-Bold", alignment=1, spaceAfter=4,
            leading=26
        ),
        "subtitle": ParagraphStyle(
            "ReportSubtitle", fontSize=10, textColor=colors.HexColor("#ccd6e0"),
            fontName="Helvetica", alignment=1, spaceAfter=2
        ),
        "section": ParagraphStyle(
            "SectionHead", fontSize=13, textColor=BLUE,
            fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6
        ),
        "body": ParagraphStyle(
            "Body", fontSize=9, textColor=BLACK,
            fontName="Helvetica", spaceAfter=4, leading=14
        ),
        "label": ParagraphStyle(
            "Label", fontSize=9, textColor=GRAY,
            fontName="Helvetica-Bold"
        ),
        "verdict_text": ParagraphStyle(
            "VerdictText", fontSize=18, fontName="Helvetica-Bold",
            alignment=1, textColor=WHITE
        ),
        "finding": ParagraphStyle(
            "Finding", fontSize=9, fontName="Helvetica",
            leftIndent=12, spaceAfter=3, textColor=BLACK
        ),
        "caption": ParagraphStyle(
            "Caption", fontSize=8, fontName="Helvetica",
            textColor=GRAY, alignment=1
        ),
        "hash_text": ParagraphStyle(
            "HashText", fontSize=7, fontName="Courier",
            textColor=DARK, alignment=1, leading=10
        ),
        "qr_title": ParagraphStyle(
            "QRTitle", fontSize=12, fontName="Helvetica-Bold",
            textColor=BLUE, alignment=1, spaceAfter=6
        ),
        "qr_instruction": ParagraphStyle(
            "QRInstruction", fontSize=8, fontName="Helvetica",
            textColor=DARK, alignment=0, leading=11
        ),
    }
    return styles


# ─────────────────────────────────────────────
#  QR CODE GENERATION
# ─────────────────────────────────────────────
def generate_hash_qrcode(document_hash, report_timestamp=None, size=200):
    """
    Generate QR code containing the document's SHA-256 hash.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )

    timestamp = report_timestamp or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    qr_data = (
        f"FORENSIC REPORT VERIFICATION\n"
        f"============================\n"
        f"Document Hash (SHA-256):\n"
        f"{document_hash}\n"
        f"============================\n"
        f"Generated: {timestamp}\n"
        f"System: AI Document Forgery Detector"
    )

    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="#1e3c72", back_color="white")
    img = img.resize((size, size), PILImage.Resampling.LANCZOS)

    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    return img_buffer


def build_verification_box(document_hash, report_timestamp, styles):
    """
    Create a styled verification box with QR code and hash.
    """
    elements = []

    elements.append(Paragraph("DOCUMENT VERIFICATION", styles["section"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dee2e6"), spaceAfter=6))

    qr_size_px = 150
    qr_buffer = generate_hash_qrcode(document_hash, report_timestamp, size=qr_size_px)
    qr_image = RLImage(qr_buffer, width=3.5 * cm, height=3.5 * cm)

    instruction_text = (
        '<b>How to Verify This Report:</b><br/><br/>'
        '<b>1.</b> Scan the QR code with your smartphone camera<br/>'
        '<b>2.</b> The QR code contains the document\'s SHA-256 hash<br/>'
        '<b>3.</b> Compare this hash with the original document<br/>'
        '<b>4.</b> If hashes match --> Report is authentic<br/>'
        '<b>5.</b> If hashes differ --> Document or report was altered<br/><br/>'
        '<font color="#dc3545"><b>WARNING: This report is only valid for the document '
        'with the exact hash shown below.</b></font>'
    )

    qr_cell = Table([[qr_image]], colWidths=[4 * cm])
    qr_cell.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))

    instruction_cell = Paragraph(instruction_text, styles["qr_instruction"])

    main_content = Table(
        [[qr_cell, instruction_cell]],
        colWidths=[4.5 * cm, 11 * cm]
    )
    main_content.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    hash_label = Paragraph("<b>Document SHA-256 Hash:</b>", styles["label"])

    if document_hash and len(document_hash) >= 64:
        hash_chunks = [document_hash[i:i + 16] for i in range(0, len(document_hash), 16)]
        hash_formatted = "  ".join(hash_chunks)
    else:
        hash_formatted = document_hash or "NO HASH AVAILABLE"

    hash_display = Paragraph(
        f'<font face="Courier" size="8" color="#1e3c72">{hash_formatted}</font>',
        styles["hash_text"]
    )

    hash_box = Table([[hash_display]], colWidths=[15.5 * cm])
    hash_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#e8f4f8")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("BOX", (0, 0), (-1, -1), 1, BLUE),
    ]))

    full_content = [
        [main_content],
        [Spacer(1, 8)],
        [hash_label],
        [Spacer(1, 4)],
        [hash_box],
    ]

    verification_table = Table(full_content, colWidths=[16 * cm])
    verification_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0f7ff")),
        ("BOX", (0, 0), (-1, -1), 2, BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))

    elements.append(verification_table)
    elements.append(Spacer(1, 12))

    return elements


# ─────────────────────────────────────────────
#  PIL IMAGE -> ReportLab Image
# ─────────────────────────────────────────────
def pil_to_rl_image(pil_img, max_width_cm=8):
    """Convert a PIL image to a ReportLab Image flowable"""
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    max_w = max_width_cm * cm
    w, h = pil_img.size
    ratio = max_w / w
    return RLImage(buf, width=max_w, height=h * ratio)


# ─────────────────────────────────────────────
#  SECTION BUILDER HELPERS
# ─────────────────────────────────────────────
def hr(styles):
    return HRFlowable(width="100%", thickness=1, color=colors.HexColor("#dee2e6"), spaceAfter=6)


def section_header(text, styles):
    return Paragraph(text, styles["section"])


def build_verdict_banner(verdict_text, confidence, risk, styles):
    """Big colored verdict box at the top of the report"""
    col = verdict_color(verdict_text)

    if verdict_text in ["GENUINE", "AUTHENTIC"]:
        label = "GENUINE"
    elif verdict_text in ["SUSPICIOUS", "POSSIBLY_FORGED"]:
        label = "SUSPICIOUS"
    else:
        label = "FORGED"

    data = [[
        Paragraph(f"{label}", styles["verdict_text"]),
    ]]
    t = Table(data, colWidths=[16 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), col),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    detail_data = [
        ["Confidence", "Risk Level"],
        [f"{confidence}%", str(risk)],
    ]
    dt = Table(detail_data, colWidths=[8 * cm, 8 * cm])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#dee2e6")),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return [t, Spacer(1, 6), dt]


def build_findings_table(findings, styles):
    """Numbered list of top findings in a shaded box"""
    if not findings:
        return [Paragraph("No findings reported.", styles["body"])]
    rows = [[Paragraph(f"{i + 1}. {f}", styles["finding"])] for i, f in enumerate(findings)]
    t = Table(rows, colWidths=[16 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3cd")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#ffc107")),
    ]))
    return [t]


def build_agent_row(label, status_suspicious, detail_text, styles):
    """One row in the agent summary table"""
    status = "SUSPICIOUS" if status_suspicious else "CLEAN"
    row_data = [
        Paragraph(label, styles["label"]),
        Paragraph(
            f'<font color="{"red" if status_suspicious else "green"}"><b>{status}</b></font>',
            styles["body"]
        ),
        Paragraph(str(detail_text)[:200], styles["body"]),
    ]
    return row_data


def build_agent_summary_table(report, styles):
    """4-agent summary table"""
    rows = [
        [Paragraph("Agent", styles["label"]),
         Paragraph("Status", styles["label"]),
         Paragraph("Key Finding", styles["label"])]
    ]

    # Vision
    vision = report.get("vision_report", {})
    rows.append(build_agent_row(
        "Vision Agent",
        vision.get("overall_suspicious", False),
        vision.get("summary", vision.get("raw_response", "See full report")[:150]),
        styles
    ))

    # OCR
    ocr = report.get("ocr_report", {})
    ocr_detail = "Text OK"
    if ocr.get("suspicious_ocr"):
        ocr_detail = "Very little text extracted"
    elif ocr.get("date_issues"):
        ocr_detail = f"Date issues: {ocr['date_issues'][0]}"
    elif ocr.get("aadhaar_validation"):
        invalid = [a for a in ocr["aadhaar_validation"] if not a.get("valid_format")]
        ocr_detail = f"Invalid Aadhaar: {invalid[0]['number']}" if invalid else "Aadhaar format valid"
    rows.append(build_agent_row("OCR Agent", ocr.get("suspicious_ocr", False), ocr_detail, styles))

    # Metadata
    meta = report.get("metadata_report", {})
    meta_detail = "No editing software detected"
    sw = meta.get("editing_software_detected", [])
    if sw:
        meta_detail = f"Software found: {sw[0].get('software_detected', 'unknown')}"
    elif meta.get("error_level_analysis", {}).get("suspicious"):
        meta_detail = meta["error_level_analysis"].get("interpretation", "High ELA variance")
    rows.append(
        build_agent_row("Metadata Agent", meta.get("overall_suspicious", False), meta_detail, styles))

    # Signature
    sig = report.get("signature_report", {})
    sig_detail = sig.get("summary", "No signature issues")[:150]
    rows.append(
        build_agent_row("Signature Agent", sig.get("overall_suspicious", False), sig_detail, styles))

    t = Table(rows, colWidths=[4 * cm, 3 * cm, 9 * cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [t]


def build_heatmap_grid(heatmaps, styles):
    """
    Enhanced heatmap grid supporting 5 heatmaps.
    Layout: 3 heatmaps in first row, 2 heatmaps in second row.
    """
    if not heatmaps:
        return [Paragraph("Heatmaps not generated.", styles["body"])]

    items = [(label, data) for label, data in heatmaps.items() if data.get("image")]
    if not items:
        return [Paragraph("No heatmap images available.", styles["body"])]

    elements = []
    num_heatmaps = len(items)

    if num_heatmaps <= 4:
        rows = []
        for i in range(0, len(items), 2):
            row_cells = []
            for j in range(2):
                if i + j < len(items):
                    label, data = items[i + j]
                    img_flowable = pil_to_rl_image(data["image"], max_width_cm=7.5)
                    caption = Paragraph(
                        f"<b>{label}</b><br/>{data.get('description', '')[:80]}",
                        styles["caption"]
                    )
                    cell_content = Table(
                        [[img_flowable], [Spacer(1, 4)], [caption]],
                        colWidths=[7.5 * cm]
                    )
                    cell_content.setStyle(TableStyle([
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ]))
                    row_cells.append(cell_content)
                else:
                    row_cells.append("")
            rows.append(row_cells)

        t = Table(rows, colWidths=[8 * cm, 8 * cm])
        t.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        elements.append(t)

    else:
        # Row 1: First 3 heatmaps
        row1_cells = []
        for i in range(min(3, num_heatmaps)):
            label, data = items[i]
            img_flowable = pil_to_rl_image(data["image"], max_width_cm=5)
            desc = data.get('description', '')[:60]
            if len(data.get('description', '')) > 60:
                desc += "..."
            caption = Paragraph(
                f"<b>{label}</b><br/><font size='7'>{desc}</font>",
                styles["caption"]
            )
            cell_content = Table(
                [[img_flowable], [Spacer(1, 3)], [caption]],
                colWidths=[5.2 * cm]
            )
            cell_content.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]))
            row1_cells.append(cell_content)

        t1 = Table([row1_cells], colWidths=[5.4 * cm, 5.4 * cm, 5.4 * cm])
        t1.setStyle(TableStyle([
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(t1)
        elements.append(Spacer(1, 8))

        # Row 2: Remaining heatmaps (4th and 5th)
        if num_heatmaps > 3:
            row2_cells = []
            for i in range(3, min(5, num_heatmaps)):
                label, data = items[i]
                img_flowable = pil_to_rl_image(data["image"], max_width_cm=6.5)
                desc = data.get('description', '')[:70]
                if len(data.get('description', '')) > 70:
                    desc += "..."
                caption = Paragraph(
                    f"<b>{label}</b><br/><font size='7'>{desc}</font>",
                    styles["caption"]
                )
                cell_content = Table(
                    [[img_flowable], [Spacer(1, 3)], [caption]],
                    colWidths=[7 * cm]
                )
                cell_content.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ]))
                row2_cells.append(cell_content)

            if len(row2_cells) == 1:
                t2 = Table([["", row2_cells[0], ""]], colWidths=[4 * cm, 8 * cm, 4 * cm])
            else:
                t2 = Table([row2_cells], colWidths=[8 * cm, 8 * cm])

            t2.setStyle(TableStyle([
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(t2)

    # Add heatmap legend
    legend_text = (
        '<b>Heatmap Color Guide:</b> '
        '<font color="#0000ff">Blue</font> = Normal/Genuine | '
        '<font color="#ffcc00">Yellow</font> = Moderate Anomaly | '
        '<font color="#ff0000">Red</font> = High Anomaly/Suspicious'
    )
    legend = Paragraph(legend_text, ParagraphStyle(
        "Legend", fontSize=8, textColor=GRAY, alignment=1
    ))
    elements.append(Spacer(1, 8))
    elements.append(legend)

    return elements


# ─────────────────────────────────────────────
#  MAIN EXPORT FUNCTION
# ─────────────────────────────────────────────
def generate_report(report, heatmaps=None, filename=None, document_name="Uploaded Document"):
    """
    Generate a forensic PDF audit report with QR code verification.

    Args:
        report       : dict -- the full report from run_all.analyze_document()
        heatmaps     : dict -- output of Heatmap.generate_all_heatmaps() (optional)
        filename     : str  -- output file path (optional, returns bytes if None)
        document_name: str  -- original filename to show in the report

    Returns:
        bytes -- PDF file bytes (for Streamlit download button)
        OR saves to filename if provided
    """
    styles = get_styles()
    buf = io.BytesIO()
    target = filename if filename else buf

    doc = SimpleDocTemplate(
        target,
        pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm,
        topMargin=2 * cm, bottomMargin=2 * cm
    )

    story = []
    now = datetime.now().strftime("%d %B %Y, %I:%M %p")

    # ══════════════════════════════════════════════════════════
    # PAGE 1: HEADER + VERDICT + QR CODE + EXPLANATION
    # ══════════════════════════════════════════════════════════

    # ── COVER HEADER (FIX: 3 ROWS not 3 COLUMNS) ─────────────
    header_data = [
        [Paragraph("FORENSIC DOCUMENT ANALYSIS REPORT", styles["title"])],
        [Paragraph(f"Generated: {now}", styles["subtitle"])],
        [Paragraph(f"Document: {document_name}", styles["subtitle"])],
    ]
    header_table = Table(header_data, colWidths=[16 * cm])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("TOPPADDING", (0, 0), (0, 0), 18),
        ("BOTTOMPADDING", (-1, -1), (-1, -1), 14),
        ("TOPPADDING", (0, 1), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -2), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 16))

    # ── VERDICT BANNER ────────────────────────────────────────
    verdict = report.get("final_verdict", {})
    verdict_text = verdict.get("verdict", "UNKNOWN")
    confidence = verdict.get("confidence_percentage", 0)
    risk = verdict.get("risk_level", "UNKNOWN")

    story.append(section_header("FINAL VERDICT", styles))
    story.extend(build_verdict_banner(verdict_text, confidence, risk, styles))
    story.append(Spacer(1, 10))

    # ── QR CODE VERIFICATION BOX ─────────────────────────────
    document_hash = report.get("document_hash")
    if document_hash and document_hash != "NO_HASH_AVAILABLE":
        story.extend(build_verification_box(document_hash, now, styles))
    else:
        no_hash_notice = Table(
            [[Paragraph(
                "WARNING: Document hash not available. QR verification cannot be generated.",
                styles["body"]
            )]],
            colWidths=[16 * cm]
        )
        no_hash_notice.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff3cd")),
            ("BOX", (0, 0), (-1, -1), 1, ORANGE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(no_hash_notice)
        story.append(Spacer(1, 10))

    # ── EXPLANATION (stays on page 1 if space) ────────────────
    explanation = verdict.get("detailed_explanation", "")
    if explanation:
        story.append(section_header("ANALYSIS EXPLANATION", styles))
        story.append(hr(styles))
        story.append(Paragraph(explanation, styles["body"]))
        story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════
    # PAGE 2: TOP FINDINGS + RECOMMENDATIONS + AGENT SUMMARY
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())

    # ── TOP FINDINGS ──────────────────────────────────────────
    findings = verdict.get("top_3_findings", [])
    story.append(section_header("TOP FINDINGS", styles))
    story.append(hr(styles))
    story.extend(build_findings_table(findings, styles))
    story.append(Spacer(1, 14))

    # ── RECOMMENDATIONS ───────────────────────────────────────
    recs = verdict.get("recommendations", [])
    if recs:
        story.append(section_header("RECOMMENDATIONS", styles))
        story.append(hr(styles))
        for rec in recs:
            story.append(Paragraph(f"- {rec}", styles["body"]))
        story.append(Spacer(1, 14))

    # ── AGENT SUMMARY TABLE ───────────────────────────────────
    story.append(section_header("AGENT ANALYSIS SUMMARY", styles))
    story.append(hr(styles))
    story.extend(build_agent_summary_table(report, styles))
    story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════
    # PAGE 3: HEATMAPS
    # ══════════════════════════════════════════════════════════
    if heatmaps:
        story.append(PageBreak())
        story.append(section_header("FORENSIC HEATMAP ANALYSIS", styles))
        story.append(hr(styles))
        story.append(Paragraph(
            "The heatmaps below highlight suspicious regions in the document using different "
            "forensic techniques. Red/yellow areas indicate potential tampering or anomalies.",
            styles["body"]
        ))
        story.append(Spacer(1, 10))
        story.extend(build_heatmap_grid(heatmaps, styles))
        story.append(Spacer(1, 8))

    # ══════════════════════════════════════════════════════════
    # PAGE 4: METADATA + BLOCKCHAIN + OCR + FOOTER
    # ══════════════════════════════════════════════════════════
    story.append(PageBreak())

    # ── METADATA DETAIL ───────────────────────────────────────
    story.append(section_header("METADATA DETAILS", styles))
    story.append(hr(styles))

    meta = report.get("metadata_report", {}).get("metadata", {})
    if meta:
        meta_rows = [[Paragraph("Field", styles["label"]), Paragraph("Value", styles["label"])]]
        for k, v in list(meta.items())[:20]:
            meta_rows.append([
                Paragraph(str(k), styles["body"]),
                Paragraph(str(v)[:120], styles["body"])
            ])
        mt = Table(meta_rows, colWidths=[5 * cm, 11 * cm])
        mt.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), DARK),
            ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(mt)
    else:
        story.append(Paragraph("No metadata available.", styles["body"]))

    story.append(Spacer(1, 14))

    # ── BLOCKCHAIN VERIFICATION ───────────────────────────────
    if document_hash:
        story.append(section_header("BLOCKCHAIN VERIFICATION", styles))
        story.append(hr(styles))

        blockchain_info = Paragraph(
            "This document's cryptographic fingerprint (SHA-256 hash) can be used for "
            "blockchain verification. Store this hash to prove the document existed in "
            "this exact form at the time of analysis.",
            styles["body"]
        )
        story.append(blockchain_info)
        story.append(Spacer(1, 6))

        hash_display = Table(
            [[Paragraph(
                f'<font face="Courier" size="8">{document_hash}</font>',
                styles["hash_text"]
            )]],
            colWidths=[16 * cm]
        )
        hash_display.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 1, BLUE),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(hash_display)
        story.append(Spacer(1, 14))

    # ── OCR EXTRACTED TEXT ────────────────────────────────────
    ocr_text = report.get("ocr_report", {}).get("extracted_text", "")
    if ocr_text and len(ocr_text.strip()) > 5:
        story.append(section_header("EXTRACTED TEXT (OCR)", styles))
        story.append(hr(styles))
        display_text = ocr_text[:1500] + ("..." if len(ocr_text) > 1500 else "")
        ocr_table = Table(
            [[Paragraph(display_text.replace("\n", "<br/>"), styles["body"])]],
            colWidths=[16 * cm]
        )
        ocr_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dee2e6")),
        ]))
        story.append(ocr_table)
        story.append(Spacer(1, 10))

    # ── FOOTER NOTE ───────────────────────────────────────────
    story.append(Spacer(1, 20))

    report_id = document_hash[:16] if document_hash else "N/A"
    footer_text = (
        f"This report was auto-generated by the AI Document Forgery Detection System "
        f"on {now}. It is intended as a forensic aid and should be reviewed by a "
        f"qualified professional before being used for legal or official purposes. "
        f"Report ID: {report_id}..."
    )
    footer_table = Table([[Paragraph(footer_text, styles["caption"])]], colWidths=[16 * cm])
    footer_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), DARK),
        ("TEXTCOLOR", (0, 0), (-1, -1), WHITE),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(footer_table)

    # ── BUILD ─────────────────────────────────────────────────
    doc.build(story)

    if not filename:
        buf.seek(0)
        return buf.read()

    return None


# ─────────────────────────────────────────────
#  STANDALONE TESTING
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("  REPORT EXPORTER - QR CODE TEST")
    print("=" * 60)

    test_hash = "a3f5c2e1d4b67890123456789012345678901234567890123456789012345678"

    print("\n[1] Testing QR code generation...")
    qr_buffer = generate_hash_qrcode(test_hash)

    with open("test_qr_code.png", "wb") as f:
        f.write(qr_buffer.getvalue())
    print("    > QR code saved to: test_qr_code.png")
    print(f"    > Encoded hash: {test_hash[:32]}...")

    print("\n[2] Generating test report with QR code...")
    test_report = {
        "document_hash": test_hash,
        "final_verdict": {
            "verdict": "SUSPICIOUS",
            "confidence_percentage": 72,
            "risk_level": "MODERATE",
            "top_3_findings": [
                "Font inconsistencies detected in signature block",
                "ELA shows re-compression artifacts in bottom-right corner",
                "Metadata contains traces of Adobe Photoshop"
            ],
            "detailed_explanation":
                "The document exhibits multiple signs of digital manipulation. "
                "The font analysis reveals inconsistencies in the signature area, "
                "and error level analysis shows regions that have been re-saved.",
            "recommendations": [
                "Request original document from issuing authority",
                "Verify signature with known authentic samples",
                "Cross-reference metadata with official records"
            ]
        },
        "vision_report": {"overall_suspicious": True, "summary": "Font mismatch detected"},
        "ocr_report": {"suspicious_ocr": False, "extracted_text": "Sample OCR text..."},
        "metadata_report": {
            "overall_suspicious": True,
            "editing_software_detected": [
                {"software_detected": "Adobe Photoshop", "field": "Creator"}
            ],
            "metadata": {"Creator": "Adobe Photoshop", "CreateDate": "2024-01-15"}
        },
        "signature_report": {
            "overall_suspicious": False, "summary": "Signature appears authentic"
        }
    }

    pdf_bytes = generate_report(
        report=test_report,
        heatmaps=None,
        filename=None,
        document_name="Test_Document.pdf"
    )

    with open("test_forensic_report.pdf", "wb") as f:
        f.write(pdf_bytes)

    print("    > Test report saved to: test_forensic_report.pdf")

    print("\n" + "=" * 60)
    print("  TEST COMPLETE!")
    print("=" * 60)
    print("\nOpen test_forensic_report.pdf and scan the QR code!")
    print(f"   It should show the document hash:\n   {test_hash}")
    print()
