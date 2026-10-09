"""SQLAlchemy ORM models for jobs and certificates."""

import uuid
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from certgen.db import Base


class JobStatus(StrEnum):
    """Job processing lifecycle states."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"


class CertificateStatus(StrEnum):
    """Individual certificate states."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class ErrorStage(StrEnum):
    """Stage where the failure occurred."""

    VALIDATION = "validation"
    GENERATION = "generation"


def utc_now() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(UTC)


def generate_uuid() -> str:
    """Generate a UUID4 hex string."""
    return str(uuid.uuid4())


class Job(Base):
    """Represents a bulk certificate generation job."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    status: Mapped[str] = mapped_column(
        String(24),
        default=JobStatus.QUEUED.value,
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(100),
        default="Certificate of Completion",
        nullable=False,
    )
    course_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
    )
    issuer_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    issue_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    signatory_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    signatory_title: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    total_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationships
    certificates: Mapped[list["Certificate"]] = relationship(
        "Certificate",
        back_populates="job",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="Certificate.sequence",
    )


class Certificate(Base):
    """Represents an individual recipient certificate within a job."""

    __tablename__ = "certificates"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=CertificateStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    raw_input: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    recipient_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    recipient_email: Mapped[str | None] = mapped_column(
        String(254),
        nullable=True,
    )
    reference_id: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )
    achievement: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    certificate_number: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        unique=True,
    )
    error_stage: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
    )
    error_code: Mapped[str | None] = mapped_column(
        String(40),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    file_path: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    file_size: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    # Relationship back to Job
    job: Mapped["Job"] = relationship("Job", back_populates="certificates")

    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_certificates_job_sequence"),
        Index("ix_certificates_job_id_status", "job_id", "status"),
    )
