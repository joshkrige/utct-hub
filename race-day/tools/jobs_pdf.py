"""Printable crew job lists, one A4 page per crew stop, from jobs_extract.py output.
Usage: python3 jobs_pdf.py jobs.json out.pdf"""
import json, re, sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                PageBreak, KeepTogether)
from reportlab.lib.styles import ParagraphStyle

data = json.load(open(sys.argv[1]))
INK, FAINT, ACC = colors.HexColor("#111111"), colors.HexColor("#666666"), colors.HexColor("#c2410c")

def rl(html):
    """App HTML -> reportlab mini-markup."""
    h = html.replace("—", "—")
    h = re.sub(r"<(?!/?b>)[^>]+>", "", h)
    return h.replace("&nbsp;", " ")

def clock(hours_from_start):
    m = int(round((4 + hours_from_start) * 60)) % (24 * 60)
    return f"{m // 60:02d}:{m % 60:02d}"

T  = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=26, leading=30, textColor=INK)
M  = ParagraphStyle("m", fontName="Helvetica", fontSize=11, leading=15, textColor=FAINT)
L  = ParagraphStyle("l", fontName="Helvetica", fontSize=11.5, leading=15.5, textColor=INK)
IT = ParagraphStyle("i", fontName="Helvetica", fontSize=12.5, leading=15.5, textColor=INK)
W  = ParagraphStyle("w", fontName="Helvetica", fontSize=11.5, leading=15.5, textColor=INK)
F  = ParagraphStyle("f", fontName="Helvetica", fontSize=8.5, leading=11, textColor=FAINT)

h = data["target"] // 3600; mnt = (data["target"] % 3600) // 60
story = []
for k, s in enumerate(data["stops"]):
    if k: story.append(PageBreak())
    story.append(Paragraph(s["s"].title() if s["s"].isupper() else s["s"], T))
    meta = f"{s['km']:g} km · planned {s['eta']} (on a {h}h{mnt:02d} pace)"
    if s["cut"]: meta += f" · <font color='#c2410c'><b>cut-off {clock(s['cut'])}</b></font>"
    story += [Spacer(1, 2*mm), Paragraph(meta, M), Spacer(1, 4*mm), Paragraph(rl(s["lead"]), L),
              Spacer(1, 5*mm)]
    rows = [["", Paragraph(rl(x), IT)] for x in s["do"]]
    t = Table(rows, colWidths=[11*mm, None])
    t.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LINEBELOW", (0,0), (-1,-2), 0.3, colors.HexColor("#dddddd")),
    ]))
    # draw the empty tick boxes
    class Boxed(Table):
        def draw(self):
            super().draw(); c = self.canv
            y = self._height
            for i, rh in enumerate(self._rowHeights):
                y -= rh
                c.setStrokeColor(INK); c.setLineWidth(1)
                c.rect(1.5*mm, y + rh - 3 - 5*mm, 5*mm, 5*mm)
    t.__class__ = Boxed
    story.append(t)
    if s["watch"]:
        w = Table([[Paragraph("<b>Watch:</b> " + rl(s["watch"]), W)]], colWidths=[None])
        w.setStyle(TableStyle([("BOX", (0,0), (-1,-1), 1.2, ACC),
                               ("BACKGROUND", (0,0), (-1,-1), colors.HexColor("#fff4ec")),
                               ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
                               ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
        story += [Spacer(1, 4*mm), KeepTogether(w)]

def foot(c, doc):
    c.saveState(); c.setFont("Helvetica", 8); c.setFillColor(FAINT)
    c.drawString(18*mm, 10*mm, f"UTCT UT100 · crew jobs · paper backup · app {data['version']}")
    c.drawRightString(A4[0] - 18*mm, 10*mm, f"page {doc.page} of {len(data['stops'])}")
    c.restoreState()

SimpleDocTemplate(sys.argv[2], pagesize=A4, leftMargin=18*mm, rightMargin=18*mm,
                  topMargin=16*mm, bottomMargin=18*mm,
                  title="UTCT crew jobs — paper backup").build(story, onFirstPage=foot, onLaterPages=foot)
