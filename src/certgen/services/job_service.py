"""Job management service handling job creation, progress calculation, and queries."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from certgen.models import Certificate, CertificateStatus, ErrorStage, Job, JobStatus
from certgen.schemas import (
    JobAcceptedOut,
    JobCreateIn,
    JobLinksOut,
    ProgressOut,
)
from certgen.services.numbering import generate_certificate_number
from certgen.services.validation import RecipientValidator, ValidatedRecipient


def build_job_links(job_id: str) -> JobLinksOut:
    """Build standard hypermedia links for a job."""
    return JobLinksOut(
        self=f"/api/v1/jobs/{job_id}",
        certificates=f"/api/v1/jobs/{job_id}/certificates",
        download=f"/api/v1/jobs/{job_id}/download",
    )


class JobService:
    """Service encapsulating job persistence, transactional creation, and progress."""

    @classmethod
    def calculate_progress(cls, session: Session, job_id: str, total_count: int) -> ProgressOut:
        """Compute live job progress using GROUP BY status query on indexed column."""
        status_counts = dict(
            session.query(Certificate.status, func.count(Certificate.id))
            .filter(Certificate.job_id == job_id)
            .group_by(Certificate.status)
            .all()
        )

        succeeded = status_counts.get(CertificateStatus.SUCCESS.value, 0)
        failed = status_counts.get(CertificateStatus.FAILED.value, 0)
        pending = status_counts.get(CertificateStatus.PENDING.value, 0)

        percent_complete = (
            round(((succeeded + failed) / total_count) * 100, 1) if total_count > 0 else 0.0
        )

        return ProgressOut(
            total=total_count,
            succeeded=succeeded,
            failed=failed,
            pending=pending,
            percent_complete=percent_complete,
        )

    @classmethod
    def create_job(
        cls,
        session: Session,
        payload: JobCreateIn,
        idempotency_key: str | None = None,
    ) -> tuple[Job, JobAcceptedOut, bool]:
        """Create a job and all recipient certificate records in a single transaction.

        Returns:
            tuple of (Job, JobAcceptedOut, has_pending_items)
        """
        # 1. Idempotency check: if key already exists, return original job
        if idempotency_key:
            existing_job = session.query(Job).filter(Job.idempotency_key == idempotency_key).first()
            if existing_job:
                progress = cls.calculate_progress(
                    session, existing_job.id, existing_job.total_count
                )
                response = JobAcceptedOut(
                    id=existing_job.id,
                    status=existing_job.status,
                    created_at=existing_job.created_at,
                    progress=progress,
                    links=build_job_links(existing_job.id),
                )
                return existing_job, response, False

        # 2. Semantic validation of each recipient
        validated_items: list[ValidatedRecipient] = RecipientValidator.validate_all(
            payload.recipients
        )

        has_pending = any(item.is_valid for item in validated_items)
        initial_status = JobStatus.QUEUED.value if has_pending else JobStatus.FAILED.value

        # 3. Insert Job record
        job = Job(
            title=payload.certificate.title,
            course_name=payload.certificate.course_name,
            issuer_name=payload.certificate.issuer_name,
            issue_date=payload.certificate.issue_date,
            signatory_name=payload.certificate.signatory_name,
            signatory_title=payload.certificate.signatory_title,
            total_count=len(payload.recipients),
            status=initial_status,
            idempotency_key=idempotency_key,
        )
        session.add(job)
        session.flush()  # Generates job.id

        # 4. Insert Certificate rows
        certificates_to_add: list[Certificate] = []
        for item in validated_items:
            if item.is_valid:
                cert = Certificate(
                    job_id=job.id,
                    sequence=item.sequence,
                    status=CertificateStatus.PENDING.value,
                    raw_input=item.raw_input,
                    recipient_name=item.name,
                    recipient_email=item.email,
                    reference_id=item.reference_id,
                    achievement=item.achievement,
                    certificate_number=generate_certificate_number(),
                    error_stage=None,
                    error_code=None,
                    error_message=None,
                )
            else:
                cert = Certificate(
                    job_id=job.id,
                    sequence=item.sequence,
                    status=CertificateStatus.FAILED.value,
                    raw_input=item.raw_input,
                    recipient_name=item.name,
                    recipient_email=item.email,
                    reference_id=item.reference_id,
                    achievement=item.achievement,
                    certificate_number=None,
                    error_stage=ErrorStage.VALIDATION.value,
                    error_code=item.error_code,
                    error_message=item.error_message,
                )
            certificates_to_add.append(cert)

        session.add_all(certificates_to_add)
        session.commit()
        session.refresh(job)

        progress = cls.calculate_progress(session, job.id, job.total_count)
        accepted_out = JobAcceptedOut(
            id=job.id,
            status=job.status,
            created_at=job.created_at,
            progress=progress,
            links=build_job_links(job.id),
        )

        return job, accepted_out, has_pending
