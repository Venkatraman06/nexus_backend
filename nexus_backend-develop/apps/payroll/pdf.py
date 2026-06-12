"""
Payslip PDF generator — matches Hackers Infotech brand.
Uses ReportLab only (no external font downloads).
"""
from io import BytesIO
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, HRFlowable,
)
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

BRAND_BLUE  = colors.HexColor("#1a237e")
BRAND_RED   = colors.HexColor("#c62828")
ACCENT_BLUE = colors.HexColor("#1565c0")
LIGHT_BLUE  = colors.HexColor("#e8eaf6")
LIGHT_RED   = colors.HexColor("#ffebee")
NET_BLUE    = colors.HexColor("#0d47a1")

W, H = A4


def _rupee(val) -> str:
    return f"Rs. {float(val):,.2f}"


def _amount_in_words(amount: Decimal) -> str:
    try:
        from num2words import num2words
        words = num2words(int(amount), lang="en_IN").title()
        paise = int((amount % 1) * 100)
        if paise:
            words += f" and {num2words(paise, lang='en_IN').title()} Paise"
        return words + " Only"
    except Exception:
        return "Amount in Words Not Available"


def generate_payslip_pdf(payroll) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15*mm, rightMargin=15*mm,
        topMargin=12*mm, bottomMargin=12*mm,
    )

    styles = getSampleStyleSheet()
    bold   = ParagraphStyle("bold",   parent=styles["Normal"], fontName="Helvetica-Bold")
    normal = ParagraphStyle("normal", parent=styles["Normal"], fontName="Helvetica", fontSize=9)
    small  = ParagraphStyle("small",  parent=styles["Normal"], fontName="Helvetica", fontSize=8, textColor=colors.grey)
    white_bold = ParagraphStyle("wb", parent=styles["Normal"], fontName="Helvetica-Bold",
                                fontSize=9, textColor=colors.white)
    white_norm = ParagraphStyle("wn", parent=styles["Normal"], fontName="Helvetica",
                                fontSize=9, textColor=colors.white)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    header_data = [[
        Paragraph("<b><font size=16 color='white'>HACKERS INFOTECH</font></b>"
                  "<br/><font size=8 color='white'>360° Cyber Defence for Digital Landscape</font>"
                  "<br/><font size=8 color='white'>ISO 9001:2015 Certified Company</font>"
                  "<br/><font size=8 color='white'>Chennai &amp; Coimbatore | +91-90424 01206</font>",
                  styles["Normal"]),
        Paragraph("<b><font size=22 color='white'>PAYSLIP</font></b>"
                  f"<br/><font size=11 color='white'>{payroll.month_name} {payroll.year}</font>",
                  ParagraphStyle("hr", parent=styles["Normal"], alignment=TA_RIGHT)),
    ]]
    header_tbl = Table(header_data, colWidths=[110*mm, 65*mm])
    header_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), BRAND_BLUE),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
        ("RIGHTPADDING", (0,0), (-1,-1), 10),
        ("TOPPADDING",   (0,0), (-1,-1), 12),
        ("BOTTOMPADDING",(0,0), (-1,-1), 12),
        ("ROUNDEDCORNERS", (0,0),(-1,-1), 4),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 6*mm))

    # ── Employee Details ──────────────────────────────────────────────────────
    emp = payroll.employee
    try:
        desig = emp.designation_ref.name if emp.designation_ref_id else (emp.designation or "—")
    except Exception:
        desig = emp.designation or "—"
    try:
        dept = emp.department_ref.name if emp.department_ref_id else (emp.department or "—")
    except Exception:
        dept = emp.department or "—"

    emp_data = [
        [Paragraph("<b>Employee Details</b>", bold), "", "", ""],
        [
            Paragraph(f"<b>Name:</b> {emp.full_name}", normal),
            "",
            Paragraph(f"<b>Division:</b> {dept}", normal),
            "",
        ],
        [
            Paragraph(f"<b>Designation:</b> {desig}", normal),
            "",
            Paragraph(f"<b>Employee ID:</b> {emp.employee_code or '—'}", normal),
            "",
        ],
    ]
    emp_tbl = Table(emp_data, colWidths=[55*mm, 30*mm, 55*mm, 35*mm])
    emp_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,0),  LIGHT_BLUE),
        ("SPAN",         (0,0), (-1,0)),
        ("SPAN",         (0,1), (1,1)),
        ("SPAN",         (2,1), (3,1)),
        ("SPAN",         (0,2), (1,2)),
        ("SPAN",         (2,2), (3,2)),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("INNERGRID",    (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(emp_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Attendance row ─────────────────────────────────────────────────────────
    att_data = [[
        Paragraph(f"<b>Working Days:</b> {payroll.working_days}", normal),
        Paragraph(f"<b>Present Days:</b> {payroll.present_days}", normal),
        Paragraph(f"<b>Leave Days:</b> {payroll.leave_days}", normal),
        Paragraph(f"<b>Month:</b> {payroll.month_name} {payroll.year}", normal),
    ]]
    att_tbl = Table(att_data, colWidths=[42*mm, 42*mm, 42*mm, 49*mm])
    att_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), LIGHT_BLUE),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("INNERGRID",    (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("TOPPADDING",   (0,0), (-1,-1), 7),
        ("BOTTOMPADDING",(0,0), (-1,-1), 7),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
    ]))
    story.append(att_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Earnings + Deductions table ───────────────────────────────────────────
    earn_head = [
        Paragraph("EARNINGS",        white_bold),
        Paragraph("Amount",          ParagraphStyle("wa", parent=white_bold, alignment=TA_RIGHT)),
        Paragraph("DEDUCTIONS",      white_bold),
        Paragraph("Amount",          ParagraphStyle("wa", parent=white_bold, alignment=TA_RIGHT)),
    ]
    earn_rows = [
        ("Basic Salary",            payroll.basic_salary,
         "Provident Fund (12% of Basic)", payroll.pf),
        ("HRA",                     payroll.hra,
         "TDS / Income Tax",        payroll.tds),
        ("Allowances",              payroll.allowances,
         "Other Deductions",        payroll.other_deductions),
        ("Overtime",                payroll.overtime,
         "Advance Deduction",       payroll.advance_deduction),
    ]
    detail_data = [earn_head]
    for el, ea, dl, da in earn_rows:
        detail_data.append([
            Paragraph(el, normal),
            Paragraph(_rupee(ea), ParagraphStyle("ra", parent=normal, alignment=TA_RIGHT)),
            Paragraph(dl, normal),
            Paragraph(_rupee(da), ParagraphStyle("ra", parent=normal, alignment=TA_RIGHT)),
        ])
    # Totals row
    detail_data.append([
        Paragraph("<b>Gross Total</b>", bold),
        Paragraph(f"<b>{_rupee(payroll.gross_total)}</b>",
                  ParagraphStyle("ra", parent=bold, alignment=TA_RIGHT)),
        Paragraph("<b>Total Deductions</b>", bold),
        Paragraph(f"<b>{_rupee(payroll.total_deductions)}</b>",
                  ParagraphStyle("ra", parent=bold, alignment=TA_RIGHT)),
    ])

    detail_tbl = Table(detail_data, colWidths=[62*mm, 30*mm, 62*mm, 21*mm])
    ts = TableStyle([
        # Header
        ("BACKGROUND",   (0,0), (1,0),  ACCENT_BLUE),
        ("BACKGROUND",   (2,0), (3,0),  BRAND_RED),
        # Totals row
        ("BACKGROUND",   (0,-1),(1,-1), LIGHT_BLUE),
        ("BACKGROUND",   (2,-1),(3,-1), LIGHT_RED),
        ("BOX",          (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("INNERGRID",    (0,0), (-1,-1), 0.3, colors.lightgrey),
        ("LINEABOVE",    (0,-1),(-1,-1), 0.8, colors.grey),
        ("TOPPADDING",   (0,0), (-1,-1), 5),
        ("BOTTOMPADDING",(0,0), (-1,-1), 5),
        ("LEFTPADDING",  (0,0), (-1,-1), 8),
        ("RIGHTPADDING", (0,0), (-1,-1), 8),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ])
    detail_tbl.setStyle(ts)
    story.append(detail_tbl)
    story.append(Spacer(1, 4*mm))

    # ── Net Salary ────────────────────────────────────────────────────────────
    net_data = [[
        Paragraph("<b><font size=11 color='white'>NET SALARY PAYABLE</font></b>", styles["Normal"]),
        Paragraph(f"<b><font size=13 color='white'>INR {float(payroll.net_salary):,.2f}</font></b>",
                  ParagraphStyle("nr", parent=styles["Normal"], alignment=TA_RIGHT)),
    ]]
    net_tbl = Table(net_data, colWidths=[120*mm, 55*mm])
    net_tbl.setStyle(TableStyle([
        ("BACKGROUND",   (0,0), (-1,-1), NET_BLUE),
        ("TOPPADDING",   (0,0), (-1,-1), 10),
        ("BOTTOMPADDING",(0,0), (-1,-1), 10),
        ("LEFTPADDING",  (0,0), (-1,-1), 12),
        ("RIGHTPADDING", (0,0), (-1,-1), 12),
        ("VALIGN",       (0,0), (-1,-1), "MIDDLE"),
    ]))
    story.append(net_tbl)
    story.append(Spacer(1, 3*mm))

    # Amount in words
    story.append(Paragraph(
        f"<i>Amount in Words: {_amount_in_words(payroll.net_salary)}</i>",
        ParagraphStyle("aiw", parent=styles["Normal"], fontSize=9, textColor=colors.grey)
    ))
    story.append(Spacer(1, 4*mm))

    # ── Payment Details ───────────────────────────────────────────────────────
    mode_label = dict(payroll.PaymentMode.choices if hasattr(payroll, "PaymentMode") else
                      [("BANK_TRANSFER","Bank Transfer"),("CASH","Cash"),
                       ("CHEQUE","Cheque"),("UPI","UPI")]
                     ).get(payroll.payment_mode, payroll.payment_mode)
    pay_parts = [f"Mode: {mode_label}", f"Status: {payroll.status.lower()}"]
    if payroll.bank_name:    pay_parts.append(f"Bank: {payroll.bank_name}")
    if payroll.account_number: pay_parts.append(f"A/C: {payroll.account_number}")

    pay_data = [[
        Paragraph("<b>Payment Details</b>", bold),
    ], [
        Paragraph("  |  ".join(pay_parts), normal),
    ]]
    pay_tbl = Table(pay_data, colWidths=[175*mm])
    pay_tbl.setStyle(TableStyle([
        ("BOX",          (0,0), (-1,-1), 0.5, colors.lightgrey),
        ("BACKGROUND",   (0,0), (-1,0),  LIGHT_BLUE),
        ("TOPPADDING",   (0,0), (-1,-1), 6),
        ("BOTTOMPADDING",(0,0), (-1,-1), 6),
        ("LEFTPADDING",  (0,0), (-1,-1), 10),
    ]))
    story.append(pay_tbl)
    story.append(Spacer(1, 5*mm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
    story.append(Spacer(1, 2*mm))
    story.append(Paragraph(
        "This is a system-generated payslip. For queries contact hr@hackersinfotech.com",
        ParagraphStyle("ft", parent=styles["Normal"], fontSize=8,
                       textColor=colors.grey, alignment=TA_CENTER)
    ))

    doc.build(story)
    return buf.getvalue()
