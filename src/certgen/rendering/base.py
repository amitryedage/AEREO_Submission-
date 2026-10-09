"""Certificate rendering interface, value objects, and rendering errors."""

from datetime import date
from typing import Protocol

from pydantic import BaseModel


class UnsupportedCharactersError(Exception):
    """Raised when text contains characters/glyphs not supported by the font."""

    pass


class RenderError(Exception):
    """Raised when PDF generation fails."""

    pass


class CertificateData(BaseModel):
    """Immutable value object containing all data needed to render a certificate."""

    title: str
    course_name: str
    issuer_name: str
    issue_date: date
    signatory_name: str | None = None
    signatory_title: str | None = None
    recipient_name: str
    achievement: str | None = None
    certificate_number: str


class CertificateRenderer(Protocol):
    """Protocol defining certificate rendering contract."""

    def render(self, data: CertificateData) -> bytes:
        """Render certificate data into PDF bytes."""
        ...
