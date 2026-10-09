"""Jobs API endpoints: creation, progress tracking, and certificate listing."""

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from certgen.api.deps import get_db, get_renderer, get_session_factory, get_storage
from certgen.errors import NotFoundError
from certgen.models import Certificate, CertificateStatus, Job
from certgen.rendering.base import CertificateRenderer
from certgen.schemas import (
    CertificateErrorOut,
    CertificateInfoIn,
    CertificateItemOut,
    CertificateListOut,
    FailureItemOut,
    JobAcceptedOut,
    JobCreateIn,
    JobDetailOut,
)
from certgen.services.archive import generate_job_archive
from certgen.services.job_service import JobService, build_job_links
from certgen.services.processor import JobProcessor
from certgen.storage.local import FileStorage

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobAcceptedOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job",
)
def create_job(
    payload: JobCreateIn,
    response: Response,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
    session_factory: sessionmaker[Session] = Depends(get_session_factory),
    renderer: CertificateRenderer = Depends(get_renderer),
    storage: FileStorage = Depends(get_storage),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> JobAcceptedOut:
    """Accept a batch of recipients, create job record, and dispatch background generation."""
    job, accepted_out, has_pending = JobService.create_job(
        session=session,
        payload=payload,
        idempotency_key=idempotency_key,
    )

    response.headers["Location"] = f"/api/v1/jobs/{job.id}"

    if has_pending:
        processor = JobProcessor(
            session_factory=session_factory,
            renderer=renderer,
            storage=storage,
        )
        background_tasks.add_task(processor.run, job.id)

    return accepted_out


@router.get(
    "/{job_id}",
    response_model=JobDetailOut,
    summary="Get job status, progress, and failure summary",
)
def get_job(job_id: str, session: Session = Depends(get_db)) -> JobDetailOut:
    """Retrieve detailed status, live progress counts, and failure preview for a job."""
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundError("JOB_NOT_FOUND", f"Job '{job_id}' not found")

    progress = JobService.calculate_progress(session, job.id, job.total_count)

    # Preview up to 20 failures
    failures_query = (
        session.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.FAILED.value,
        )
        .order_by(Certificate.sequence)
    )
    total_failures = failures_query.count()
    failure_rows = failures_query.limit(20).all()

    failures_preview = [
        FailureItemOut(
            sequence=c.sequence,
            recipient_name=c.recipient_name,
            recipient_email=c.recipient_email,
            error_stage=c.error_stage or "unknown",
            error_code=c.error_code or "UNKNOWN",
            error_message=c.error_message or "Unknown failure",
        )
        for c in failure_rows
    ]

    cert_info = CertificateInfoIn(
        title=job.title,
        course_name=job.course_name,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        signatory_name=job.signatory_name,
        signatory_title=job.signatory_title,
    )

    return JobDetailOut(
        id=job.id,
        status=job.status,
        certificate=cert_info,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        progress=progress,
        failures=failures_preview,
        failures_truncated=total_failures > 20,
        links=build_job_links(job.id),
    )


@router.get(
    "/{job_id}/certificates",
    response_model=CertificateListOut,
    summary="List certificates belonging to a job",
)
def list_job_certificates(
    job_id: str,
    status_filter: str | None = Query(None, alias="status", pattern="^(pending|success|failed)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> CertificateListOut:
    """Retrieve paginated certificates with optional status filtering."""
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundError("JOB_NOT_FOUND", f"Job '{job_id}' not found")

    query = session.query(Certificate).filter(Certificate.job_id == job_id)
    if status_filter:
        query = query.filter(Certificate.status == status_filter)

    total_items = query.count()
    items = (
        query.order_by(Certificate.sequence).offset((page - 1) * page_size).limit(page_size).all()
    )

    out_items: list[CertificateItemOut] = []
    for c in items:
        download_url = (
            f"/api/v1/certificates/{c.id}/download"
            if c.status == CertificateStatus.SUCCESS.value
            else None
        )
        err = (
            CertificateErrorOut(
                stage=c.error_stage or "unknown",
                code=c.error_code or "UNKNOWN",
                message=c.error_message or "",
            )
            if c.status == CertificateStatus.FAILED.value
            else None
        )

        out_items.append(
            CertificateItemOut(
                id=c.id,
                sequence=c.sequence,
                status=c.status,
                certificate_number=c.certificate_number,
                recipient_name=c.recipient_name,
                recipient_email=c.recipient_email,
                reference_id=c.reference_id,
                download_url=download_url,
                generated_at=c.generated_at,
                error=err,
            )
        )

    return CertificateListOut(
        job_id=job.id,
        page=page,
        page_size=page_size,
        total_items=total_items,
        items=out_items,
    )


@router.get(
    "/{job_id}/download",
    summary="Download all successful certificates for a job as a ZIP archive",
)
def download_job_archive(
    job_id: str,
    session: Session = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> StreamingResponse:
    """Stream a ZIP archive containing all generated certificates and manifest.csv."""
    spooled_file, zip_filename = generate_job_archive(session, storage, job_id)

    def file_stream():
        try:
            while chunk := spooled_file.read(64 * 1024):
                yield chunk
        finally:
            spooled_file.close()

    return StreamingResponse(
        file_stream(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
