"""ZIP archive generation with SpooledTemporaryFile and manifest CSV."""

import csv
import io
import tempfile
import zipfile
from typing import BinaryIO

from sqlalchemy.orm import Session

from certgen.errors import ConflictError, NotFoundError
from certgen.models import Certificate, CertificateStatus, Job
from certgen.storage.local import FileStorage


def generate_job_archive(
    session: Session,
    storage: FileStorage,
    job_id: str,
) -> tuple[BinaryIO, str]:
    """Build a ZIP archive of all successful certificates plus a manifest CSV.

    Returns:
        tuple of (file_object, download_filename)
    """
    job = session.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise NotFoundError("JOB_NOT_FOUND", f"Job '{job_id}' not found")

    certificates = (
        session.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.sequence)
        .all()
    )

    success_certs = [c for c in certificates if c.status == CertificateStatus.SUCCESS.value]
    if not success_certs:
        raise ConflictError(
            "NO_CERTIFICATES_AVAILABLE",
            "No successful certificates are available for download in this job.",
        )

    # Use SpooledTemporaryFile to spill to disk if archive exceeds 10MB
    spooled = tempfile.SpooledTemporaryFile(max_size=10 * 1024 * 1024, mode="w+b")

    with zipfile.ZipFile(spooled, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Add PDF files for all successful certificates
        for cert in success_certs:
            if cert.file_path and storage.exists(cert.file_path):
                with storage.open(cert.file_path) as f:
                    pdf_data = f.read()
                filename = f"{cert.certificate_number or cert.id}.pdf"
                zf.writestr(filename, pdf_data)

        # 2. Build manifest CSV listing all certificates in request sequence
        manifest_buffer = io.StringIO()
        writer = csv.writer(manifest_buffer)
        writer.writerow(
            [
                "sequence",
                "name",
                "email",
                "certificate_number",
                "status",
                "error_stage",
                "error_code",
                "error_message",
            ]
        )

        for cert in certificates:
            writer.writerow(
                [
                    cert.sequence,
                    cert.recipient_name or "",
                    cert.recipient_email or "",
                    cert.certificate_number or "",
                    cert.status,
                    cert.error_stage or "",
                    cert.error_code or "",
                    cert.error_message or "",
                ]
            )

        zf.writestr("manifest.csv", manifest_buffer.getvalue().encode("utf-8"))

    spooled.seek(0)
    short_id = job.id[:8]
    zip_filename = f"job-{short_id}-certificates.zip"

    return spooled, zip_filename
