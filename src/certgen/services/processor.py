"""Background job processor executing sequential certificate generation with failure isolation."""

import logging

from sqlalchemy.orm import Session, sessionmaker

from certgen.models import Certificate, CertificateStatus, ErrorStage, Job, JobStatus, utc_now
from certgen.rendering.base import (
    CertificateData,
    CertificateRenderer,
    UnsupportedCharactersError,
)
from certgen.storage.local import FileStorage, StorageError

logger = logging.getLogger("certgen.processor")


class JobProcessor:
    """Worker service that processes pending certificates in the background."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        renderer: CertificateRenderer,
        storage: FileStorage,
    ) -> None:
        self.session_factory = session_factory
        self.renderer = renderer
        self.storage = storage

    def run(self, job_id: str) -> None:
        """Execute generation for all pending certificates in a job."""
        session: Session = self.session_factory()
        try:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                logger.warning("Job %s not found for processing", job_id)
                return

            # Mark job processing
            job.status = JobStatus.PROCESSING.value
            if not job.started_at:
                job.started_at = utc_now()
            session.commit()

            try:
                # Query only pending certificates ordered by sequence
                pending_ids = [
                    row[0]
                    for row in session.query(Certificate.id)
                    .filter(
                        Certificate.job_id == job_id,
                        Certificate.status == CertificateStatus.PENDING.value,
                    )
                    .order_by(Certificate.sequence)
                    .all()
                ]

                for cert_id in pending_ids:
                    cert = session.query(Certificate).filter(Certificate.id == cert_id).first()
                    if not cert or cert.status != CertificateStatus.PENDING.value:
                        continue

                    try:
                        data = CertificateData(
                            title=job.title,
                            course_name=job.course_name,
                            issuer_name=job.issuer_name,
                            issue_date=job.issue_date,
                            signatory_name=job.signatory_name,
                            signatory_title=job.signatory_title,
                            recipient_name=cert.recipient_name or "",
                            achievement=cert.achievement,
                            certificate_number=cert.certificate_number or "",
                        )

                        pdf_bytes = self.renderer.render(data)
                        storage_key = f"{job.id}/{cert.id}.pdf"
                        self.storage.save(storage_key, pdf_bytes)

                        cert.status = CertificateStatus.SUCCESS.value
                        cert.file_path = storage_key
                        cert.file_size = len(pdf_bytes)
                        cert.generated_at = utc_now()
                        cert.error_stage = None
                        cert.error_code = None
                        cert.error_message = None

                    except UnsupportedCharactersError as e:
                        cert.status = CertificateStatus.FAILED.value
                        cert.error_stage = ErrorStage.GENERATION.value
                        cert.error_code = "UNSUPPORTED_CHARACTERS"
                        cert.error_message = str(e)

                    except StorageError as e:
                        cert.status = CertificateStatus.FAILED.value
                        cert.error_stage = ErrorStage.GENERATION.value
                        cert.error_code = "STORAGE_ERROR"
                        cert.error_message = str(e)

                    except Exception as e:
                        logger.exception("Rendering exception on cert %s", cert_id)
                        cert.status = CertificateStatus.FAILED.value
                        cert.error_stage = ErrorStage.GENERATION.value
                        cert.error_code = "RENDER_ERROR"
                        cert.error_message = f"Generation failed: {e}"

                    # Commit per certificate for live progress and crash resilience
                    session.commit()

            except Exception:
                logger.exception("Job %s crashed during execution", job_id)
                # Mark any remaining pending items as aborted
                session.query(Certificate).filter(
                    Certificate.job_id == job_id,
                    Certificate.status == CertificateStatus.PENDING.value,
                ).update(
                    {
                        Certificate.status: CertificateStatus.FAILED.value,
                        Certificate.error_stage: ErrorStage.GENERATION.value,
                        Certificate.error_code: "PROCESSING_ABORTED",
                        Certificate.error_message: "Processing aborted due to unexpected job crash",
                    },
                    synchronize_session=False,
                )
                session.commit()

            finally:
                # Always finalize job status
                succeeded = (
                    session.query(Certificate)
                    .filter(
                        Certificate.job_id == job_id,
                        Certificate.status == CertificateStatus.SUCCESS.value,
                    )
                    .count()
                )
                failed = (
                    session.query(Certificate)
                    .filter(
                        Certificate.job_id == job_id,
                        Certificate.status == CertificateStatus.FAILED.value,
                    )
                    .count()
                )

                if succeeded > 0 and failed == 0:
                    job.status = JobStatus.COMPLETED.value
                elif succeeded > 0 and failed > 0:
                    job.status = JobStatus.COMPLETED_WITH_ERRORS.value
                else:
                    job.status = JobStatus.FAILED.value

                job.completed_at = utc_now()
                session.commit()

        finally:
            session.close()
