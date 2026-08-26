import io
import os
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

# ── Fonts ──────────────────────────────────────────────────────────────────────
_FONT_PATH_R = "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf"
_FONT_PATH_B = "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf"
_WIN_FONT_R  = "C:/Windows/Fonts/arial.ttf"
_WIN_FONT_B  = "C:/Windows/Fonts/arialbd.ttf"

if os.path.exists(_FONT_PATH_R):
    pdfmetrics.registerFont(TTFont("AppFont",     _FONT_PATH_R))
    pdfmetrics.registerFont(TTFont("AppFontBold", _FONT_PATH_B))
    _FONT      = "AppFont"
    _FONT_BOLD = "AppFontBold"
elif os.path.exists(_WIN_FONT_R):
    pdfmetrics.registerFont(TTFont("AppFont",     _WIN_FONT_R))
    pdfmetrics.registerFont(TTFont("AppFontBold", _WIN_FONT_B))
    _FONT      = "AppFont"
    _FONT_BOLD = "AppFontBold"
else:
    _FONT      = "Helvetica"
    _FONT_BOLD = "Helvetica-Bold"

# ── Palette ────────────────────────────────────────────────────────────────────
C_NAVY        = colors.HexColor("#0F1B3D")   # deep navy — primary
C_ACCENT      = colors.HexColor("#3B82F6")   # bright blue — accent stripe
C_GOLD        = colors.HexColor("#F59E0B")   # warm gold — fine accent
C_WHITE       = colors.white

C_DEBIT       = colors.HexColor("#DC2626")   # red — debit
C_DEBIT_BG    = colors.HexColor("#FEF2F2")
C_DEBIT_TINT  = colors.HexColor("#FFE4E4")

C_CREDIT      = colors.HexColor("#059669")   # emerald — credit
C_CREDIT_BG   = colors.HexColor("#ECFDF5")
C_CREDIT_TINT = colors.HexColor("#D1FAE5")

C_AMBER       = colors.HexColor("#D97706")   # amber — net balance
C_AMBER_BG    = colors.HexColor("#FFFBEB")

C_BLUE_TINT   = colors.HexColor("#EFF6FF")
C_ALT_ROW     = colors.HexColor("#F8FAFC")
C_BORDER      = colors.HexColor("#E2E8F0")
C_TEXT_MUTED  = colors.HexColor("#64748B")

PAGE_W, PAGE_H = A4
MARGIN  = 15 * mm
_BODY_W = PAGE_W - 2 * MARGIN   # 180 mm


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fmt_inr(amount: float) -> str:
    if amount == 0:
        return "—"
    integer = str(int(round(abs(amount))))
    if len(integer) > 3:
        last3 = integer[-3:]
        rest  = integer[:-3]
        groups = []
        while len(rest) > 2:
            groups.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.append(rest)
        groups.reverse()
        integer = ",".join(groups) + "," + last3
    sign = "-" if amount < 0 else ""
    return f"{sign}₹{integer}"


def _para(text, font=None, size=8, color=colors.black, align=0) -> Paragraph:
    style = ParagraphStyle(
        "c",
        fontName=font or _FONT,
        fontSize=size,
        textColor=color,
        alignment=align,
        leading=size * 1.35,
        wordWrap="LTR",
    )
    return Paragraph(str(text), style)


# ── Page template (header + footer) ────────────────────────────────────────────

def _build_doc(buf: io.BytesIO, title: str, subtitle: str, metadata: dict):
    def draw_page(canvas, doc):
        canvas.saveState()

        # ── Header band ──
        header_h = 36 * mm
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, PAGE_H - header_h, PAGE_W, header_h, fill=1, stroke=0)

        # Layered top accent
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, PAGE_H - 2.6 * mm, PAGE_W, 2.6 * mm, fill=1, stroke=0)
        canvas.setFillColor(C_GOLD)
        canvas.rect(0, PAGE_H - 3.1 * mm, PAGE_W, 0.5 * mm, fill=1, stroke=0)

        # Title
        canvas.setFillColor(C_WHITE)
        canvas.setFont(_FONT_BOLD, 16)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - 14.5 * mm, title)

        # Subtitle
        canvas.setFont(_FONT, 10)
        canvas.drawCentredString(PAGE_W / 2, PAGE_H - 22 * mm, subtitle)

        # Meta line (period + account)
        if metadata.get("date_range"):
            canvas.setFont(_FONT, 7.8)
            meta = (
                f"Period:  {metadata['date_range']}      •      "
                f"Account:  {metadata.get('account') or 'N/A'}"
            )
            canvas.drawCentredString(PAGE_W / 2, PAGE_H - 28 * mm, meta)

        # Decorative gold underline below header text
        canvas.setStrokeColor(C_GOLD)
        canvas.setLineWidth(0.4)
        canvas.line(PAGE_W / 2 - 30 * mm, PAGE_H - 31 * mm,
                    PAGE_W / 2 + 30 * mm, PAGE_H - 31 * mm)

        # ── Footer band ──
        footer_h = 11 * mm
        canvas.setFillColor(C_NAVY)
        canvas.rect(0, 0, PAGE_W, footer_h, fill=1, stroke=0)
        canvas.setFillColor(C_ACCENT)
        canvas.rect(0, footer_h, PAGE_W, 0.7 * mm, fill=1, stroke=0)

        canvas.setFillColor(C_WHITE)
        canvas.setFont(_FONT_BOLD, 7)
        canvas.drawString(MARGIN, 4.5 * mm, "KHATABOOK  REPORT")
        canvas.setFont(_FONT, 7)
        canvas.drawCentredString(
            PAGE_W / 2, 4.5 * mm,
            f"Generated  ·  {datetime.now().strftime('%d %b %Y · %H:%M')}",
        )
        canvas.drawRightString(PAGE_W - MARGIN, 4.5 * mm, f"Page {doc.page}")

        canvas.restoreState()

    frame = Frame(
        MARGIN, 13 * mm,
        _BODY_W, PAGE_H - 38 * mm - 13 * mm,
        leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0,
    )
    template = PageTemplate(id="main", frames=[frame], onPage=draw_page)
    return BaseDocTemplate(
        buf,
        pagesize=A4,
        pageTemplates=[template],
        topMargin=38 * mm,
        bottomMargin=13 * mm,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
    )


# ── Grouped Report ─────────────────────────────────────────────────────────────

def generate_grouped_pdf(transactions: list, code: str, metadata: dict) -> bytes:
    filtered = [t for t in transactions if t["area_code"] == code]

    totals: dict[str, dict] = {}
    for t in filtered:
        pn = t["party_name"]
        if pn not in totals:
            totals[pn] = {"debit": 0.0, "credit": 0.0}
        totals[pn]["debit"]  += t["debit"]
        totals[pn]["credit"] += t["credit"]

    parties = sorted(totals.items(), key=lambda x: x[1]["debit"], reverse=True)
    grand_debit  = sum(v["debit"]  for _, v in parties)
    grand_credit = sum(v["credit"] for _, v in parties)
    grand_net    = grand_debit - grand_credit

    # 8 + 60 + 16 + 32 + 32 + 32 = 180 mm
    col_w = [8*mm, 60*mm, 16*mm, 32*mm, 32*mm, 32*mm]

    header = ["#", "Party Name", "Code", "Total Debit  ₹", "Total Credit  ₹", "Net  ₹"]
    rows = [header]
    for i, (party, v) in enumerate(parties, 1):
        net = v["debit"] - v["credit"]
        rows.append([
            str(i),
            _para(party, size=8),
            code,
            _para(_fmt_inr(v["debit"]),  font=_FONT_BOLD, size=8.5, color=C_DEBIT,  align=2),
            _para(_fmt_inr(v["credit"]), font=_FONT_BOLD, size=8.5, color=C_CREDIT, align=2),
            _para(_fmt_inr(abs(net)),    font=_FONT_BOLD, size=8.5, align=2),
        ])

    net_label = (
        "—" if grand_net == 0
        else f"{_fmt_inr(abs(grand_net))} {'Dr' if grand_net > 0 else 'Cr'}"
    )
    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "",
        _para(_fmt_inr(grand_debit),  font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(_fmt_inr(grand_credit), font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(net_label,              font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    style = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (3, 0), (3, 0),  C_DEBIT),
        ("BACKGROUND", (4, 0), (4, 0),  C_CREDIT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        # Data rows
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 8),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (0, last), "CENTER"),
        ("ALIGN",  (2, 1), (2, last), "CENTER"),
        # Grand total
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Grouped Summary",
        f"Area Code  ·  {code}    •    {len(parties)} Parties    •    Total Debit: {_fmt_inr(grand_debit)}",
        metadata,
    )
    doc.build([Spacer(1, 6 * mm), table])
    return buf.getvalue()


# ── Detailed Report ────────────────────────────────────────────────────────────

def generate_detailed_pdf(transactions: list, code: str, metadata: dict) -> bytes:
    filtered = [t for t in transactions if t["area_code"] == code]

    grand_debit  = sum(t["debit"]  for t in filtered)
    grand_credit = sum(t["credit"] for t in filtered)
    grand_net    = grand_debit - grand_credit
    net_str = (
        "—" if grand_net == 0
        else f"{_fmt_inr(abs(grand_net))} {'Dr' if grand_net > 0 else 'Cr'}"
    )

    # ── Summary cards (4 cards across full width) ─────────────────────────────
    card_w = [_BODY_W / 4] * 4
    summary_data = [
        ["TRANSACTIONS", "TOTAL DEBIT  (–)", "TOTAL CREDIT  (+)", "NET BALANCE"],
        [str(len(filtered)), _fmt_inr(grand_debit), _fmt_inr(grand_credit), net_str],
    ]

    card_style = [
        # Top accent stripe per card (3 pt thick, colored)
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_DEBIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_CREDIT),
        ("LINEABOVE", (3, 0), (3, 0), 3.5, C_AMBER),

        # Label row — small uppercase, colored, white background
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_DEBIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_CREDIT),
        ("TEXTCOLOR", (3, 0), (3, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),

        # Value row — large bold, tinted background
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_DEBIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_CREDIT),
        ("TEXTCOLOR", (3, 1), (3, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_DEBIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_CREDIT_BG),
        ("BACKGROUND",(3, 1), (3, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),

        # Borders
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]

    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Transaction table — with running balance column ──────────────────────
    # 8 + 19 + 38 + 15 + 24 + 24 + 24 + 28 = 180 mm
    col_w = [8*mm, 19*mm, 38*mm, 15*mm, 24*mm, 24*mm, 24*mm, 28*mm]

    header = ["S.No", "Date", "Party Name", "City", "Bill Ref",
              "Debit  ₹", "Credit  ₹", "Balance  ₹"]
    rows = [header]
    running = 0.0
    for i, t in enumerate(filtered, 1):
        running += t["debit"] - t["credit"]
        if running == 0:
            bal_text = "—"
            bal_color = colors.black
        else:
            bal_text = f"{_fmt_inr(abs(running))} {'Dr' if running > 0 else 'Cr'}"
            bal_color = C_DEBIT if running > 0 else C_CREDIT
        rows.append([
            str(i),
            t["date"],
            _para(t["party_name"], size=7.7),
            _para(t.get("city", ""), size=7.7, color=C_TEXT_MUTED),
            _para(t["details"] or "—", size=7.5, color=C_TEXT_MUTED),
            _para(_fmt_inr(t["debit"])  if t["debit"]  else "—",
                  font=_FONT_BOLD, size=8.5, color=C_DEBIT,  align=2),
            _para(_fmt_inr(t["credit"]) if t["credit"] else "—",
                  font=_FONT_BOLD, size=8.5, color=C_CREDIT, align=2),
            _para(bal_text, font=_FONT_BOLD, size=8.2, color=bal_color, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "", "", "",
        _para(_fmt_inr(grand_debit),  font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
        _para(_fmt_inr(grand_credit), font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
        _para(net_str,                font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    tx_style = [
        # Header row
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (5, 0), (5, 0),  C_DEBIT),
        ("BACKGROUND", (6, 0), (6, 0),  C_CREDIT),
        ("BACKGROUND", (7, 0), (7, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),

        # Data rows
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 7.7),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),

        # Center S.No + Date columns
        ("ALIGN", (0, 1), (1, last - 1), "CENTER"),

        # Subtle background tint on running-balance column
        ("BACKGROUND", (7, 1), (7, last - 1), C_AMBER_BG),

        # Grand total row
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
        ("ALIGN",  (0, last), (-1, last), "CENTER"),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            tx_style.append(("BACKGROUND", (0, i), (6, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(tx_style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Detailed Statement",
        f"Area Code  ·  {code}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Sales Only Report ──────────────────────────────────────────────────────────

def generate_sales_only_pdf(transactions: list, code: str, metadata: dict) -> bytes:
    filtered = [t for t in transactions if t["area_code"] == code and t["debit"] > 0]

    total_sales = sum(t["debit"] for t in filtered)
    avg_sale    = total_sales / len(filtered) if filtered else 0.0

    # ── Summary cards (3 across full width) ──────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["SALE ENTRIES", "TOTAL SALES  (–)", "AVERAGE SALE"],
        [str(len(filtered)), _fmt_inr(total_sales), _fmt_inr(avg_sale)],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_DEBIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_DEBIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_DEBIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_DEBIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Transaction table — debit entries only, no credit column ─────────────
    # 8 + 19 + 45 + 18 + 26 + 32 + 32 = 180 mm
    col_w = [8*mm, 19*mm, 45*mm, 18*mm, 26*mm, 32*mm, 32*mm]
    header = ["S.No", "Date", "Party Name", "City", "Bill Ref", "Sale  ₹", "Running Total  ₹"]
    rows   = [header]
    running = 0.0
    for i, t in enumerate(filtered, 1):
        running += t["debit"]
        rows.append([
            str(i),
            t["date"],
            _para(t["party_name"], size=7.7),
            _para(t.get("city", ""), size=7.7, color=C_TEXT_MUTED),
            _para(t["details"] or "—", size=7.5, color=C_TEXT_MUTED),
            _para(_fmt_inr(t["debit"]), font=_FONT_BOLD, size=8.5, color=C_DEBIT, align=2),
            _para(_fmt_inr(running),    font=_FONT_BOLD, size=8.2, color=C_AMBER, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "", "", "",
        _para(_fmt_inr(total_sales), font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
        "",
    ])

    last = len(rows) - 1
    tx_style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (5, 0), (5, 0),  C_DEBIT),
        ("BACKGROUND", (6, 0), (6, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 7.7),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (1, last - 1), "CENTER"),
        ("BACKGROUND", (6, 1), (6, last - 1), C_AMBER_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
        ("ALIGN",  (0, last), (-1, last), "CENTER"),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            tx_style.append(("BACKGROUND", (0, i), (5, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(tx_style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Sales Only",
        f"Area Code  ·  {code}    •    {len(filtered)} Sales    •    Total: {_fmt_inr(total_sales)}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Pre-Diwali Outstanding Report ──────────────────────────────────────────────

def generate_outstanding_pdf(transactions: list, code: str, cutoff: datetime, metadata: dict) -> bytes:
    from datetime import datetime as _dt

    def _parse_tx_date(s: str):
        try:
            return _dt.strptime(s.strip(), "%d %b %Y")
        except ValueError:
            return None

    cutoff_str = cutoff.strftime("%d %b %Y")

    # Pass 1 — collect pre-cutoff debits per party (strict: date must be before cutoff)
    pre_debit: dict[str, float] = {}
    for t in transactions:
        if t["area_code"] != code:
            continue
        if t["debit"] <= 0:
            continue
        tx_date = _parse_tx_date(t["date"])
        if tx_date is None or tx_date >= cutoff:
            continue
        pn = t["party_name"]
        pre_debit[pn] = pre_debit.get(pn, 0.0) + t["debit"]

    # Pass 2 — collect ALL credits per party (no date restriction)
    total_credit: dict[str, float] = {}
    for t in transactions:
        if t["area_code"] != code:
            continue
        if t["credit"] <= 0:
            continue
        pn = t["party_name"]
        total_credit[pn] = total_credit.get(pn, 0.0) + t["credit"]

    # Only parties that had pre-cutoff sales AND still have a positive balance
    outstanding = [
        (pn, pre_debit[pn], total_credit.get(pn, 0.0),
         pre_debit[pn] - total_credit.get(pn, 0.0))
        for pn in pre_debit
        if pre_debit[pn] - total_credit.get(pn, 0.0) > 0
    ]

    if not outstanding:
        raise ValueError(
            f"No outstanding payments found before {cutoff_str} for area code {code}."
        )

    outstanding.sort(key=lambda x: x[3], reverse=True)

    grand_pre    = sum(o[1] for o in outstanding)
    grand_paid   = sum(o[2] for o in outstanding)
    grand_remain = sum(o[3] for o in outstanding)

    # ── Table: 8 + 62 + 14 + 34 + 34 + 28 = 180 mm ───────────────────────────
    col_w = [8*mm, 62*mm, 14*mm, 34*mm, 34*mm, 28*mm]
    header = ["#", "Party Name", "Code", "Pre-Cutoff Sales  ₹", "Total Payments  ₹", "Outstanding  ₹"]
    rows = [header]
    for i, (pn, pre, paid, remain) in enumerate(outstanding, 1):
        rows.append([
            str(i),
            _para(pn, size=8),
            code,
            _para(_fmt_inr(pre),  font=_FONT_BOLD, size=8.5, color=C_DEBIT,  align=2),
            _para(_fmt_inr(paid) if paid else "—", font=_FONT_BOLD, size=8.5, color=C_CREDIT, align=2),
            _para(_fmt_inr(remain), font=_FONT_BOLD, size=8.5, color=C_AMBER, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "",
        _para(_fmt_inr(grand_pre),    font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(_fmt_inr(grand_paid),   font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(_fmt_inr(grand_remain), font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (3, 0), (3, 0),  C_DEBIT),
        ("BACKGROUND", (4, 0), (4, 0),  C_CREDIT),
        ("BACKGROUND", (5, 0), (5, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 8),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (0, last), "CENTER"),
        ("ALIGN",  (2, 1), (2, last), "CENTER"),
        ("BACKGROUND", (5, 1), (5, last - 1), C_AMBER_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (4, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Pre-Diwali Outstanding",
        f"Area Code  ·  {code}    •    Cutoff: {cutoff_str}    •    Outstanding: {_fmt_inr(grand_remain)}",
        metadata,
    )
    doc.build([Spacer(1, 6 * mm), table])
    return buf.getvalue()


# ── Payment Only Report ────────────────────────────────────────────────────────

def generate_payment_only_pdf(transactions: list, code: str, metadata: dict) -> bytes:
    filtered = [t for t in transactions if t["area_code"] == code and t["credit"] > 0]

    total_payments = sum(t["credit"] for t in filtered)
    avg_payment    = total_payments / len(filtered) if filtered else 0.0

    # ── Summary cards ─────────────────────────────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["PAYMENT ENTRIES", "TOTAL PAYMENTS  (+)", "AVERAGE PAYMENT"],
        [str(len(filtered)), _fmt_inr(total_payments), _fmt_inr(avg_payment)],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_CREDIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_CREDIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_CREDIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_CREDIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Transaction table — credit entries only, no debit column ──────────────
    # 8 + 19 + 45 + 18 + 26 + 32 + 32 = 180 mm
    col_w = [8*mm, 19*mm, 45*mm, 18*mm, 26*mm, 32*mm, 32*mm]
    header = ["S.No", "Date", "Party Name", "City", "Bill Ref", "Payment  ₹", "Running Total  ₹"]
    rows   = [header]
    running = 0.0
    for i, t in enumerate(filtered, 1):
        running += t["credit"]
        rows.append([
            str(i),
            t["date"],
            _para(t["party_name"], size=7.7),
            _para(t.get("city", ""), size=7.7, color=C_TEXT_MUTED),
            _para(t["details"] or "—", size=7.5, color=C_TEXT_MUTED),
            _para(_fmt_inr(t["credit"]), font=_FONT_BOLD, size=8.5, color=C_CREDIT, align=2),
            _para(_fmt_inr(running),     font=_FONT_BOLD, size=8.2, color=C_AMBER,  align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "", "", "",
        _para(_fmt_inr(total_payments), font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
        "",
    ])

    last = len(rows) - 1
    tx_style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (5, 0), (5, 0),  C_CREDIT),
        ("BACKGROUND", (6, 0), (6, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 7.7),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (1, last - 1), "CENTER"),
        ("BACKGROUND", (6, 1), (6, last - 1), C_AMBER_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
        ("ALIGN",  (0, last), (-1, last), "CENTER"),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            tx_style.append(("BACKGROUND", (0, i), (5, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(tx_style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Payments Only",
        f"Area Code  ·  {code}    •    {len(filtered)} Payments    •    Total: {_fmt_inr(total_payments)}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Full PDF Sale Filter (all area codes, debits only) ─────────────────────────

def generate_full_sales_pdf(transactions: list, metadata: dict) -> bytes:
    filtered    = [t for t in transactions if t["debit"] > 0]
    total_sales = sum(t["debit"] for t in filtered)
    codes       = sorted(set(t["area_code"] for t in filtered))

    # ── Summary cards ─────────────────────────────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["SALE ENTRIES", "TOTAL SALES  (–)", "AREA CODES"],
        [str(len(filtered)), _fmt_inr(total_sales), str(len(codes))],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_DEBIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_DEBIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_DEBIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_DEBIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Transaction table — all sales across all codes ─────────────────────────
    # 8 + 16 + 14 + 40 + 15 + 20 + 32 + 35 = 180 mm
    col_w = [8*mm, 16*mm, 14*mm, 40*mm, 15*mm, 20*mm, 32*mm, 35*mm]
    header = ["S.No", "Date", "Code", "Party Name", "City", "Bill Ref", "Sale  ₹", "Running Total  ₹"]
    rows   = [header]
    running = 0.0
    for i, t in enumerate(filtered, 1):
        running += t["debit"]
        rows.append([
            str(i),
            t["date"],
            t["area_code"],
            _para(t["party_name"], size=7.7),
            _para(t.get("city", ""), size=7.7, color=C_TEXT_MUTED),
            _para(t["details"] or "—", size=7.5, color=C_TEXT_MUTED),
            _para(_fmt_inr(t["debit"]), font=_FONT_BOLD, size=8.5, color=C_DEBIT, align=2),
            _para(_fmt_inr(running),    font=_FONT_BOLD, size=8.2, color=C_AMBER, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL", font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        "", "", "", "",
        _para(_fmt_inr(total_sales), font=_FONT_BOLD, size=9.5, color=C_WHITE, align=2),
        "",
    ])

    last = len(rows) - 1
    tx_style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (6, 0), (6, 0),  C_DEBIT),
        ("BACKGROUND", (7, 0), (7, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("FONTNAME", (0, 1), (-1, last - 1), _FONT),
        ("FONTSIZE", (0, 1), (-1, last - 1), 7.7),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (2, last - 1), "CENTER"),
        ("BACKGROUND", (7, 1), (7, last - 1), C_AMBER_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
        ("ALIGN",  (0, last), (-1, last), "CENTER"),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            tx_style.append(("BACKGROUND", (0, i), (6, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(tx_style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Full PDF Sale Filter",
        f"All Area Codes    •    {len(filtered)} Sale Entries    •    Total: {_fmt_inr(total_sales)}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Sales Analysis (all codes, one row per code) ───────────────────────────────

def generate_analysis_pdf(transactions: list, metadata: dict) -> bytes:
    code_data: dict[str, dict] = {}
    for t in transactions:
        if t["debit"] <= 0:
            continue
        c = t["area_code"]
        if c not in code_data:
            code_data[c] = {"count": 0, "total": 0.0}
        code_data[c]["count"] += 1
        code_data[c]["total"] += t["debit"]

    if not code_data:
        raise ValueError("No sale entries found in this PDF.")

    grand_total = sum(v["total"] for v in code_data.values())
    grand_count = sum(v["count"] for v in code_data.values())
    rows_data   = sorted(code_data.items(), key=lambda x: x[1]["total"], reverse=True)

    # ── Summary cards ─────────────────────────────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["TOTAL SALE ENTRIES", "GRAND TOTAL SALES  (–)", "AREA CODES"],
        [str(grand_count), _fmt_inr(grand_total), str(len(code_data))],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_DEBIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_DEBIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_DEBIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_DEBIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Analysis table: 8 + 50 + 28 + 60 + 34 = 180 mm ───────────────────────
    col_w = [8*mm, 50*mm, 28*mm, 60*mm, 34*mm]
    header = ["#", "Area Code", "Sale Entries", "Total Sales  ₹", "Share  %"]
    rows = [header]
    for i, (code, v) in enumerate(rows_data, 1):
        share = v["total"] / grand_total * 100 if grand_total else 0
        rows.append([
            str(i),
            _para(code, font=_FONT_BOLD, size=10, color=C_NAVY),
            _para(str(v["count"]), size=9, align=1),
            _para(_fmt_inr(v["total"]), font=_FONT_BOLD, size=9.5, color=C_DEBIT, align=2),
            _para(f"{share:.1f}%",      font=_FONT_BOLD, size=9,   color=C_TEXT_MUTED, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL",        font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        _para(str(grand_count),     font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        _para(_fmt_inr(grand_total),font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para("100%",               font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (3, 0), (3, 0),  C_DEBIT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (0, last), "CENTER"),
        ("BACKGROUND", (3, 1), (3, last - 1), C_DEBIT_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (2, i), C_ALT_ROW))
            style.append(("BACKGROUND", (4, i), (4, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Sales Analysis",
        f"All Area Codes    •    {len(code_data)} Codes    •    Grand Total: {_fmt_inr(grand_total)}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Payment Analysis (all codes, one row per code) ─────────────────────────────

def generate_payment_analysis_pdf(transactions: list, metadata: dict) -> bytes:
    code_data: dict[str, dict] = {}
    for t in transactions:
        if t["credit"] <= 0:
            continue
        c = t["area_code"]
        if c not in code_data:
            code_data[c] = {"count": 0, "total": 0.0}
        code_data[c]["count"] += 1
        code_data[c]["total"] += t["credit"]

    if not code_data:
        raise ValueError("No payment entries found in this PDF.")

    grand_total = sum(v["total"] for v in code_data.values())
    grand_count = sum(v["count"] for v in code_data.values())
    rows_data   = sorted(code_data.items(), key=lambda x: x[1]["total"], reverse=True)

    # ── Summary cards ─────────────────────────────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["TOTAL PAYMENT ENTRIES", "GRAND TOTAL PAYMENTS  (+)", "AREA CODES"],
        [str(grand_count), _fmt_inr(grand_total), str(len(code_data))],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_ACCENT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_CREDIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_NAVY),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_CREDIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_NAVY),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_CREDIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_BLUE_TINT),
        ("BACKGROUND",(1, 1), (1, 1),  C_CREDIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Analysis table: 8 + 50 + 28 + 60 + 34 = 180 mm ───────────────────────
    col_w = [8*mm, 50*mm, 28*mm, 60*mm, 34*mm]
    header = ["#", "Area Code", "Payment Entries", "Total Payments  ₹", "Share  %"]
    rows = [header]
    for i, (code, v) in enumerate(rows_data, 1):
        share = v["total"] / grand_total * 100 if grand_total else 0
        rows.append([
            str(i),
            _para(code, font=_FONT_BOLD, size=10, color=C_NAVY),
            _para(str(v["count"]), size=9, align=1),
            _para(_fmt_inr(v["total"]), font=_FONT_BOLD, size=9.5, color=C_CREDIT, align=2),
            _para(f"{share:.1f}%",      font=_FONT_BOLD, size=9,   color=C_TEXT_MUTED, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL",        font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        _para(str(grand_count),     font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        _para(_fmt_inr(grand_total),font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para("100%",               font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (3, 0), (3, 0),  C_CREDIT),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (0, last), "CENTER"),
        ("BACKGROUND", (3, 1), (3, last - 1), C_CREDIT_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (2, i), C_ALT_ROW))
            style.append(("BACKGROUND", (4, i), (4, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Payment Analysis",
        f"All Area Codes    •    {len(code_data)} Codes    •    Grand Total: {_fmt_inr(grand_total)}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()


# ── Outstanding Analysis (debit − credit per area code) ────────────────────────

def generate_outstanding_analysis_pdf(transactions: list, metadata: dict) -> bytes:
    code_data: dict[str, dict] = {}
    for t in transactions:
        c = t["area_code"]
        if c not in code_data:
            code_data[c] = {"debit": 0.0, "credit": 0.0}
        code_data[c]["debit"]  += t["debit"]
        code_data[c]["credit"] += t["credit"]

    if not code_data:
        raise ValueError("No transactions found in this PDF.")

    grand_debit   = sum(v["debit"]  for v in code_data.values())
    grand_credit  = sum(v["credit"] for v in code_data.values())
    grand_net     = grand_debit - grand_credit

    # Sort by outstanding descending (highest first)
    rows_data = sorted(code_data.items(), key=lambda x: x[1]["debit"] - x[1]["credit"], reverse=True)

    net_label = (
        "—" if grand_net == 0
        else f"{_fmt_inr(abs(grand_net))} {'Dr' if grand_net > 0 else 'Cr'}"
    )

    # ── Summary cards ─────────────────────────────────────────────────────────
    card_w = [_BODY_W / 3] * 3
    summary_data = [
        ["TOTAL SALES  (–)", "TOTAL PAYMENTS  (+)", "NET OUTSTANDING"],
        [_fmt_inr(grand_debit), _fmt_inr(grand_credit), net_label],
    ]
    card_style = [
        ("LINEABOVE", (0, 0), (0, 0), 3.5, C_DEBIT),
        ("LINEABOVE", (1, 0), (1, 0), 3.5, C_CREDIT),
        ("LINEABOVE", (2, 0), (2, 0), 3.5, C_AMBER),
        ("FONTNAME",  (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",  (0, 0), (-1, 0), 7.2),
        ("ALIGN",     (0, 0), (-1, 0), "CENTER"),
        ("BACKGROUND",(0, 0), (-1, 0), C_WHITE),
        ("TEXTCOLOR", (0, 0), (0, 0),  C_DEBIT),
        ("TEXTCOLOR", (1, 0), (1, 0),  C_CREDIT),
        ("TEXTCOLOR", (2, 0), (2, 0),  C_AMBER),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
        ("FONTNAME",  (0, 1), (-1, 1), _FONT_BOLD),
        ("FONTSIZE",  (0, 1), (-1, 1), 14),
        ("ALIGN",     (0, 1), (-1, 1), "CENTER"),
        ("TEXTCOLOR", (0, 1), (0, 1),  C_DEBIT),
        ("TEXTCOLOR", (1, 1), (1, 1),  C_CREDIT),
        ("TEXTCOLOR", (2, 1), (2, 1),  C_AMBER),
        ("BACKGROUND",(0, 1), (0, 1),  C_DEBIT_BG),
        ("BACKGROUND",(1, 1), (1, 1),  C_CREDIT_BG),
        ("BACKGROUND",(2, 1), (2, 1),  C_AMBER_BG),
        ("TOPPADDING",    (0, 1), (-1, 1), 9),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 13),
        ("VALIGN",     (0, 0), (-1, -1), "MIDDLE"),
        ("INNERGRID",  (0, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBEFORE", (0, 0), (0, -1),  0.4, C_BORDER),
        ("LINEAFTER",  (-1, 0), (-1, -1), 0.4, C_BORDER),
        ("LINEBELOW",  (0, -1), (-1, -1), 0.4, C_BORDER),
    ]
    summary_table = Table(summary_data, colWidths=card_w)
    summary_table.setStyle(TableStyle(card_style))

    # ── Analysis table: 8 + 50 + 42 + 42 + 38 = 180 mm ───────────────────────
    col_w = [8*mm, 50*mm, 42*mm, 42*mm, 38*mm]
    header = ["#", "Area Code", "Total Sales  ₹", "Total Payments  ₹", "Outstanding  ₹"]
    rows = [header]
    for i, (code, v) in enumerate(rows_data, 1):
        net = v["debit"] - v["credit"]
        net_str   = "—" if net == 0 else f"{_fmt_inr(abs(net))} {'Dr' if net > 0 else 'Cr'}"
        net_color = C_AMBER if net > 0 else (C_CREDIT if net < 0 else colors.black)
        rows.append([
            str(i),
            _para(code, font=_FONT_BOLD, size=10, color=C_NAVY),
            _para(_fmt_inr(v["debit"]),  font=_FONT_BOLD, size=9.5, color=C_DEBIT,  align=2),
            _para(_fmt_inr(v["credit"]), font=_FONT_BOLD, size=9.5, color=C_CREDIT, align=2),
            _para(net_str,               font=_FONT_BOLD, size=9.5, color=net_color, align=2),
        ])

    rows.append([
        "",
        _para("GRAND TOTAL",         font=_FONT_BOLD, size=10, color=C_WHITE, align=1),
        _para(_fmt_inr(grand_debit),  font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(_fmt_inr(grand_credit), font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
        _para(net_label,              font=_FONT_BOLD, size=10, color=C_WHITE, align=2),
    ])

    last = len(rows) - 1
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), C_NAVY),
        ("BACKGROUND", (2, 0), (2, 0),  C_DEBIT),
        ("BACKGROUND", (3, 0), (3, 0),  C_CREDIT),
        ("BACKGROUND", (4, 0), (4, 0),  C_AMBER),
        ("TEXTCOLOR",  (0, 0), (-1, 0), C_WHITE),
        ("FONTNAME",   (0, 0), (-1, 0), _FONT_BOLD),
        ("FONTSIZE",   (0, 0), (-1, 0), 8.5),
        ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
        ("TOPPADDING",    (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 9),
        ("TOPPADDING",    (0, 1), (-1, last - 1), 10),
        ("BOTTOMPADDING", (0, 1), (-1, last - 1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID",   (0, 0), (-1, -1), 0.4, C_BORDER),
        ("ALIGN",  (0, 1), (0, last), "CENTER"),
        ("BACKGROUND", (2, 1), (2, last - 1), C_DEBIT_BG),
        ("BACKGROUND", (3, 1), (3, last - 1), C_CREDIT_BG),
        ("BACKGROUND", (4, 1), (4, last - 1), C_AMBER_BG),
        ("BACKGROUND", (0, last), (-1, last), C_NAVY),
        ("LINEABOVE",  (0, last), (-1, last), 1.5, C_GOLD),
        ("TOPPADDING",    (0, last), (-1, last), 10),
        ("BOTTOMPADDING", (0, last), (-1, last), 10),
    ]
    for i in range(1, last):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (1, i), C_ALT_ROW))

    table = Table(rows, colWidths=col_w, repeatRows=1)
    table.setStyle(TableStyle(style))

    buf = io.BytesIO()
    doc = _build_doc(
        buf,
        "Khatabook  ·  Outstanding Analysis",
        f"All Area Codes    •    Net Outstanding: {net_label}",
        metadata,
    )
    doc.build([
        Spacer(1, 5 * mm),
        summary_table,
        Spacer(1, 8 * mm),
        table,
    ])
    return buf.getvalue()
