"""
PCS Platform - Base PDF Report Generator

All module PDF generators inherit from this class.
Provides: font registration, style init, table builder, cover page, footer.
Subclass only needs to implement _build_content().
"""

import os
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, grey, lightgrey
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, Image
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class BaseReportGenerator:
    """Base PDF report generator — shared by all calculation modules"""

    PAGE_SIZE = A4
    ML, MR, MT, MB = 25*mm, 20*mm, 20*mm, 20*mm

    C_PRIMARY = HexColor("#0078d4")
    C_DARK = HexColor("#1a1a1a")
    C_GREEN = HexColor("#107c10")
    C_RED = HexColor("#d83b01")
    C_BG_LIGHT = HexColor("#f5f8fc")
    C_BG_GREY = HexColor("#f5f5f5")

    def __init__(self, title: str = "计算书", author: str = "PCS计算平台 v1.0.5"):
        self._pdf_title = title
        self._pdf_author = author
        self._register_fonts()
        self._init_styles()

    # ========================================================================
    # Font & Style (shared by all subclasses)
    # ========================================================================

    def _register_fonts(self):
        """Auto-detect Chinese font on Windows"""
        for fn, fp in [("MicrosoftYaHei", "C:/Windows/Fonts/msyh.ttc"),
                        ("SimHei", "C:/Windows/Fonts/simhei.ttf"),
                        ("SimSun", "C:/Windows/Fonts/simsun.ttc")]:
            if os.path.exists(fp):
                try:
                    pdfmetrics.registerFont(TTFont(fn, fp))
                    self._cn = fn
                    return
                except Exception:
                    continue
        self._cn = "Helvetica"

    def _init_styles(self):
        """Create standard paragraph styles"""
        fn = self._cn
        self.s = {
            'cover': ParagraphStyle('cv', fontName=fn, fontSize=24, leading=32,
                                     alignment=TA_CENTER, textColor=self.C_PRIMARY,
                                     spaceAfter=12*mm),
            'cover_sub': ParagraphStyle('cs', fontName=fn, fontSize=14, leading=20,
                                         alignment=TA_CENTER, textColor=self.C_DARK,
                                         spaceAfter=6*mm),
            'h1': ParagraphStyle('h1', fontName=fn, fontSize=16, leading=22,
                                  textColor=self.C_PRIMARY, spaceBefore=10*mm,
                                  spaceAfter=5*mm),
            'h2': ParagraphStyle('h2', fontName=fn, fontSize=13, leading=18,
                                  textColor=self.C_DARK, spaceBefore=6*mm,
                                  spaceAfter=3*mm),
            'body': ParagraphStyle('bd', fontName=fn, fontSize=10, leading=16,
                                    textColor=self.C_DARK, spaceAfter=2*mm,
                                    alignment=TA_JUSTIFY),
            'formula': ParagraphStyle('fm', fontName='Courier', fontSize=9, leading=14,
                                       textColor=black, backColor=self.C_BG_GREY,
                                       borderPadding=6, spaceBefore=2*mm,
                                       spaceAfter=2*mm, leftIndent=8*mm),
            'result': ParagraphStyle('rs', fontName=fn, fontSize=10, leading=16,
                                      textColor=self.C_GREEN, spaceAfter=2*mm,
                                      leftIndent=4*mm),
            'warning': ParagraphStyle('wn', fontName=fn, fontSize=10, leading=16,
                                       textColor=self.C_RED, spaceAfter=2*mm,
                                       leftIndent=4*mm),
            'cell': ParagraphStyle('cl', fontName=fn, fontSize=9, leading=13,
                                    textColor=black),
            'cell_hdr': ParagraphStyle('ch', fontName=fn, fontSize=9, leading=13,
                                        textColor=white),
            'footer': ParagraphStyle('ft', fontName=fn, fontSize=8, leading=10,
                                      textColor=grey, alignment=TA_CENTER),
        }

    # ========================================================================
    # Paragraph helpers — create styled Paragraph objects
    # ========================================================================

    def h1(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['h1'])

    def h2(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['h2'])

    def body(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['body'])

    def formula(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['formula'])

    def result(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['result'])

    def warn(self, text: str) -> Paragraph:
        return Paragraph(text, self.s['warning'])

    # ========================================================================
    # Table builder (shared)
    # ========================================================================

    def table(self, data: list, hdr_rows: int = 1) -> Table:
        """Build a formatted table with alternating row colors"""
        fd = [[Paragraph(str(c), self.s['cell_hdr'] if i < hdr_rows else self.s['cell'])
               for c in r] for i, r in enumerate(data)]
        n = len(data[0])
        w = self.PAGE_SIZE[0] - self.ML - self.MR
        t = Table(fd, colWidths=[w / n] * n)
        cmds = [('GRID', (0, 0), (-1, -1), 0.5, lightgrey),
                 ('BOX', (0, 0), (-1, -1), 1, self.C_PRIMARY)]
        for i in range(hdr_rows):
            cmds.extend([('BACKGROUND', (0, i), (-1, i), self.C_PRIMARY),
                          ('TEXTCOLOR', (0, i), (-1, i), white),
                          ('BOTTOMPADDING', (0, i), (-1, i), 6),
                          ('TOPPADDING', (0, i), (-1, i), 6)])
        for i in range(hdr_rows, len(data)):
            if i % 2 == 0:
                cmds.append(('BACKGROUND', (0, i), (-1, i), self.C_BG_LIGHT))
        cmds.extend([('TOPPADDING', (0, hdr_rows), (-1, -1), 4),
                      ('BOTTOMPADDING', (0, hdr_rows), (-1, -1), 4)])
        t.setStyle(TableStyle(cmds))
        return t

    # ========================================================================
    # Cover page (shared)
    # ========================================================================

    def cover(self, story: list, title: str, subtitle: str = "",
               extra_info: str = ""):
        """Append standard cover page to story"""
        story.append(Spacer(1, 40 * mm))
        story.append(Paragraph(title, self.s['cover']))
        if subtitle:
            story.append(Paragraph(subtitle, self.s['cover_sub']))
        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(width="60%", thickness=1, color=self.C_PRIMARY))
        story.append(Spacer(1, 15 * mm))
        story.append(Paragraph(
            f"生成日期: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}",
            self.s['body']))
        if extra_info:
            story.append(Paragraph(extra_info, self.s['body']))
        story.append(Paragraph(
            f"平台版本: {self._pdf_author}", self.s['body']))
        story.append(PageBreak())

    # ========================================================================
    # Calculation steps (shared rendering)
    # ========================================================================

    def render_steps(self, story: list, steps: list):
        """Render calculation steps with formula/substitution/result/note"""
        for step in steps:
            story.append(Paragraph(
                f"<b>第{step.step_num}步: {step.title}</b>", self.s['body']))
            story.append(Paragraph(f"公式: {step.formula_text}", self.s['formula']))
            story.append(Paragraph(f"代入: {step.substitution}", self.s['body']))
            story.append(Paragraph(
                f"<b>结果: {step.result} {step.unit}</b>", self.s['result']))
            if step.note:
                story.append(Paragraph(
                    f"<i>说明: {step.note}</i>", self.s['body']))
            story.append(Spacer(1, 2 * mm))

    # ========================================================================
    # Footer (shared)
    # ========================================================================

    def footer(self, story: list):
        """Append standard end-of-report footer"""
        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(width="100%", thickness=0.5, color=lightgrey))
        story.append(Paragraph("--- 计算书结束 ---", self.s['footer']))
        story.append(Paragraph(
            f"本计算书由 PCS计算平台 v1.0.5 自动生成于 "
            f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            self.s['footer']))

    # ========================================================================
    # Embed image helper
    # ========================================================================

    def embed_image(self, img_bytes: bytes, width: float = 160,
                     height: float = 90) -> Image:
        """Create an Image flowable from PNG bytes"""
        return Image(BytesIO(img_bytes), width=width * mm, height=height * mm)

    # ========================================================================
    # Build & save
    # ========================================================================

    def build(self, filepath: str, story: list):
        """Build PDF from story and save to filepath"""
        doc = SimpleDocTemplate(
            filepath, pagesize=self.PAGE_SIZE,
            leftMargin=self.ML, rightMargin=self.MR,
            topMargin=self.MT, bottomMargin=self.MB,
            title=self._pdf_title, author=self._pdf_author)
        doc.build(story)
