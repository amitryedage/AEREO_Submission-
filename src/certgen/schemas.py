"""Pydantic schemas for request validation and response serialization."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CertificateInfoIn(BaseModel):
    """Envelope certificate metadata for the batch."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        default="Certificate of Completion",
        min_length=1,
        max_length=100,
        description="Certificate title",
    )
    course_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Name of the course, training, or event",
    )
    issuer_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Organization issuing the certificate",
    )
    issue_date: date = Field(
        ...,
        description="Official issue date (YYYY-MM-DD)",
    )
    signatory_name: str | None = Field(
        default=None,
        max_length=100,
        description="Name of the signing official",
    )
    signatory_title: str | None = Field(
        default=None,
        max_length=100,
        description="Title of the signing official",
    )

    @field_validator("signatory_name", "signatory_title", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        """Convert empty strings to None."""
        if isinstance(v, str) and not v.strip():
            return None
        return v


class JobCreateIn(BaseModel):
    """Top-level envelope request for bulk certificate generation."""

    certificate: CertificateInfoIn
    recipients: list[Any] = Field(
        ...,
        description="List of recipient objects",
    )

    @field_validator("recipients")
    @classmethod
    def validate_recipients_envelope(cls, v: list[Any]) -> list[Any]:
        """Validate recipient list size boundary."""
        if not isinstance(v, list) or len(v) == 0:
            raise ValueError("must contain at least 1 item")
        # Default maximum constraint (1000 items)
        if len(v) > 1000:
            raise ValueError("exceeds maximum allowed limit of 1000 recipients")
        return v


class ProgressOut(BaseModel):
    """Progress metrics for a job."""

    total: int
    succeeded: int
    failed: int
    pending: int
    percent_complete: float


class JobLinksOut(BaseModel):
    """Hypermedia links for job polling and downloading."""

    self: str
    certificates: str
    download: str


class JobAcceptedOut(BaseModel):
    """Response returned immediately upon job acceptance (HTTP 202)."""

    id: str
    status: str
    created_at: datetime
    progress: ProgressOut
    links: JobLinksOut


class FailureItemOut(BaseModel):
    """Failure summary item in job status preview."""

    sequence: int
    recipient_name: str | None = None
    recipient_email: str | None = None
    error_stage: str
    error_code: str
    error_message: str


class JobDetailOut(BaseModel):
    """Detailed job status and progress response."""

    id: str
    status: str
    certificate: CertificateInfoIn
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    progress: ProgressOut
    failures: list[FailureItemOut] = Field(default_factory=list)
    failures_truncated: bool = False
    links: JobLinksOut


class JobListOut(BaseModel):
    """Paginated list of bulk generation jobs."""

    page: int
    page_size: int
    total_items: int
    items: list[JobDetailOut]


class CertificateErrorOut(BaseModel):
    """Structured error payload for failed certificates."""

    stage: str
    code: str
    message: str


class CertificateItemOut(BaseModel):
    """Individual certificate metadata in listing."""

    id: str
    sequence: int
    status: str
    certificate_number: str | None = None
    recipient_name: str | None = None
    recipient_email: str | None = None
    reference_id: str | None = None
    download_url: str | None = None
    generated_at: datetime | None = None
    error: CertificateErrorOut | None = None


class CertificateDetailOut(CertificateItemOut):
    """Detailed single certificate response."""

    job_id: str
    file_size: int | None = None


class CertificateListOut(BaseModel):
    """Paginated certificate list response."""

    job_id: str
    page: int
    page_size: int
    total_items: int
    items: list[CertificateItemOut]
