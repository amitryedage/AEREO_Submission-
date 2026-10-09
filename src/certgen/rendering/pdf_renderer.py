"""ReportLab implementation of certificate rendering with A4 landscape template."""

import contextlib
import io
from pathlib import Path
from typing import ClassVar

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from certgen.rendering.base import (
    CertificateData,
    CertificateRenderer,
    RenderError,
    UnsupportedCharactersError,
)

FONTS_DIR = Path(__file__).parent / "assets" / "fonts"

# Palette
BORDER_COLOR = colors.HexColor("#1E3A8A")  # Deep Blue
SECONDARY_COLOR = colors.HexColor("#3B82F6")  # Accent Blue
TEXT_PRIMARY = colors.HexColor("#0F172A")  # Slate 900
TEXT_SECONDARY = colors.HexColor("#475569")  # Slate 600
TEXT_MUTED = colors.HexColor("#64748B")  # Slate 500
RULE_COLOR = colors.HexColor("#CBD5E1")  # Light Slate
ACHIEVEMENT_COLOR = colors.HexColor("#B45309")  # Amber 700


class ReportLabCertificateRenderer(CertificateRenderer):
    """Generates elegant A4 landscape PDF certificates using ReportLab."""

    _fonts_registered: ClassVar[bool] = False

    def __init__(self) -> None:
        self._ensure_fonts_registered()

    @classmethod
    def _ensure_fonts_registered(cls) -> None:
        """Register DejaVu font family once."""
        if cls._fonts_registered:
            return

        font_mappings = {
            "DejaVuSerif": FONTS_DIR / "DejaVuSerif.ttf",
            "DejaVuSerif-Bold": FONTS_DIR / "DejaVuSerif-Bold.ttf",
            "DejaVuSerif-Italic": FONTS_DIR / "DejaVuSerif-Italic.ttf",
        }

        for font_name, font_path in font_mappings.items():
            if font_path.exists():
                with contextlib.suppress(Exception):
                    pdfmetrics.registerFont(TTFont(font_name, str(font_path)))

        cls._fonts_registered = True

    def _check_glyph_coverage(self, text: str, font_name: str = "DejaVuSerif") -> None:
        """Verify that every character in the text is supported by the font."""
        try:
            font = pdfmetrics.getFont(font_name)
            char_to_glyph = getattr(font.face, "charToGlyph", {})
        except Exception:
            return

        unsupported = [c for c in text if ord(c) not in char_to_glyph]
        if unsupported:
            unique_unsupported = "".join(sorted(set(unsupported)))
            raise UnsupportedCharactersError(
                f"Font '{font_name}' does not support characters: {unique_unsupported}"
            )

    def _validate_data(self, data: CertificateData) -> None:
        """Validate glyph support for all dynamic text fields."""
        fields_to_check = [
            (data.title, "DejaVuSerif-Bold"),
            (data.course_name, "DejaVuSerif-Bold"),
            (data.issuer_name, "DejaVuSerif"),
            (data.recipient_name, "DejaVuSerif-Bold"),
            (data.certificate_number, "DejaVuSerif"),
        ]
        if data.achievement:
            fields_to_check.append((data.achievement, "DejaVuSerif-Italic"))
        if data.signatory_name:
            fields_to_check.append((data.signatory_name, "DejaVuSerif-Bold"))
        if data.signatory_title:
            fields_to_check.append((data.signatory_title, "DejaVuSerif-Italic"))

        for text, font in fields_to_check:
            self._check_glyph_coverage(text, font)

    def render(self, data: CertificateData) -> bytes:
        """Render certificate data into PDF bytes."""
        try:
            self._validate_data(data)

            buf = io.BytesIO()
            page_width, page_height = landscape(A4)  # 841.89 x 595.27 pt
            c = canvas.Canvas(buf, pagesize=(page_width, page_height))
            c.setTitle(f"Certificate - {data.recipient_name}")

            # 1. Draw Decorative Borders
            self._draw_borders(c, page_width, page_height)

            # 2. Issuer Name
            c.setFont("DejaVuSerif", 16)
            c.setFillColor(TEXT_SECONDARY)
            c.drawCentredString(page_width / 2, 495, data.issuer_name.upper())

            # 3. Certificate Title
            c.setFont("DejaVuSerif-Bold", 32)
            c.setFillColor(BORDER_COLOR)
            c.drawCentredString(page_width / 2, 450, data.title)

            # 4. Presentation Line
            c.setFont("DejaVuSerif-Italic", 14)
            c.setFillColor(TEXT_SECONDARY)
            c.drawCentredString(page_width / 2, 405, "This certificate is proudly presented to")

            # 5. Recipient Name with dynamic shrink-to-fit
            name_y = 345
            self._draw_recipient_name(c, data.recipient_name, page_width / 2, name_y, max_width=640)

            # 6. Horizontal Divider Under Name
            c.setStrokeColor(RULE_COLOR)
            c.setLineWidth(1)
            c.line(page_width / 2 - 200, name_y - 12, page_width / 2 + 200, name_y - 12)

            # 7. Completion Line
            c.setFont("DejaVuSerif", 13)
            c.setFillColor(TEXT_SECONDARY)
            c.drawCentredString(page_width / 2, 305, "for successfully completing")

            # 8. Course Name (with wrapping and font fitting)
            course_bottom_y = self._draw_course_name(
                c, data.course_name, page_width / 2, 270, max_width=640
            )

            # 9. Optional Achievement
            if data.achievement:
                c.setFont("DejaVuSerif-Italic", 15)
                c.setFillColor(ACHIEVEMENT_COLOR)
                c.drawCentredString(page_width / 2, course_bottom_y - 25, data.achievement)

            # 10. Bottom Left: Issue Date
            date_str = f"Date: {data.issue_date.strftime('%d %B %Y')}"
            c.setFont("DejaVuSerif", 11)
            c.setFillColor(TEXT_SECONDARY)
            c.drawString(60, 90, date_str)

            # 11. Bottom Right: Signatory block (if provided)
            if data.signatory_name:
                sig_x = page_width - 240
                c.setStrokeColor(TEXT_MUTED)
                c.setLineWidth(1)
                c.line(sig_x, 115, sig_x + 180, 115)  # Signature line

                c.setFont("DejaVuSerif-Bold", 12)
                c.setFillColor(TEXT_PRIMARY)
                c.drawCentredString(sig_x + 90, 95, data.signatory_name)

                if data.signatory_title:
                    c.setFont("DejaVuSerif-Italic", 10)
                    c.setFillColor(TEXT_MUTED)
                    c.drawCentredString(sig_x + 90, 80, data.signatory_title)

            # 12. Bottom Center: Unique Certificate Number
            c.setFont("DejaVuSerif", 9)
            c.setFillColor(TEXT_MUTED)
            c.drawCentredString(page_width / 2, 45, f"Certificate No. {data.certificate_number}")

            c.showPage()
            c.save()

            return buf.getvalue()

        except UnsupportedCharactersError:
            raise
        except Exception as e:
            raise RenderError(f"Failed to render certificate PDF: {e}") from e

    def _draw_borders(self, c: canvas.Canvas, width: float, height: float) -> None:
        """Draw nested decorative borders."""
        # Outer thick border
        c.setStrokeColor(BORDER_COLOR)
        c.setLineWidth(3.0)
        c.rect(22, 22, width - 44, height - 44, stroke=1, fill=0)

        # Inner thin border
        c.setStrokeColor(SECONDARY_COLOR)
        c.setLineWidth(1.0)
        c.rect(28, 28, width - 56, height - 56, stroke=1, fill=0)

        # Corner accents
        accent_len = 16
        c.setStrokeColor(BORDER_COLOR)
        c.setLineWidth(2.0)
        # Top-left
        c.line(32, height - 32, 32 + accent_len, height - 32)
        c.line(32, height - 32, 32, height - 32 - accent_len)
        # Top-right
        c.line(width - 32, height - 32, width - 32 - accent_len, height - 32)
        c.line(width - 32, height - 32, width - 32, height - 32 - accent_len)
        # Bottom-left
        c.line(32, 32, 32 + accent_len, 32)
        c.line(32, 32, 32, 32 + accent_len)
        # Bottom-right
        c.line(width - 32, 32, width - 32 - accent_len, 32)
        c.line(width - 32, 32, width - 32, 32 + accent_len)

    def _draw_recipient_name(
        self,
        c: canvas.Canvas,
        name: str,
        center_x: float,
        y: float,
        max_width: float,
    ) -> None:
        """Draw recipient name starting at 40pt, auto-shrinking down to 20pt to fit."""
        font_name = "DejaVuSerif-Bold"
        font_size = 40
        while font_size > 20:
            text_width = pdfmetrics.stringWidth(name, font_name, font_size)
            if text_width <= max_width:
                break
            font_size -= 1

        c.setFont(font_name, font_size)
        c.setFillColor(TEXT_PRIMARY)
        c.drawCentredString(center_x, y, name)

    def _draw_course_name(
        self,
        c: canvas.Canvas,
        course_name: str,
        center_x: float,
        y: float,
        max_width: float,
    ) -> float:
        """Draw course name wrapped to max 2 lines, shrinking font if needed. Return lowest Y."""
        font_name = "DejaVuSerif-Bold"
        font_size = 23
        lines: list[str] = []

        while font_size >= 14:
            lines = simpleSplit(course_name, font_name, font_size, max_width)
            if len(lines) <= 2:
                break
            font_size -= 1

        c.setFont(font_name, font_size)
        c.setFillColor(TEXT_PRIMARY)

        line_height = font_size + 6
        current_y = y
        for line in lines[:2]:
            c.drawCentredString(center_x, current_y, line)
            current_y -= line_height

        return current_y + line_height
