"""Certificates API endpoints: metadata and individual PDF download."""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from certgen.api.deps import get_db, get_storage
from certgen.errors import ConflictError, NotFoundError
from certgen.models import Certificate, CertificateStatus
from certgen.schemas import CertificateDetailOut, CertificateErrorOut
from certgen.storage.local import FileStorage

logger = logging.getLogger("certgen.certificates")

router = APIRouter(prefix="/api/v1/certificates", tags=["Certificates"])


@router.get(
    "/{certificate_id}",
    response_model=CertificateDetailOut,
    summary="Get single certificate metadata",
)
def get_certificate(
    certificate_id: str,
    session: Session = Depends(get_db),
) -> CertificateDetailOut:
    """Retrieve metadata for a specific certificate."""
    cert = session.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", f"Certificate '{certificate_id}' not found")

    download_url = (
        f"/api/v1/certificates/{cert.id}/download"
        if cert.status == CertificateStatus.SUCCESS.value
        else None
    )
    err = (
        CertificateErrorOut(
            stage=cert.error_stage or "unknown",
            code=cert.error_code or "UNKNOWN",
            message=cert.error_message or "",
        )
        if cert.status == CertificateStatus.FAILED.value
        else None
    )

    return CertificateDetailOut(
        id=cert.id,
        job_id=cert.job_id,
        sequence=cert.sequence,
        status=cert.status,
        certificate_number=cert.certificate_number,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        reference_id=cert.reference_id,
        download_url=download_url,
        file_size=cert.file_size,
        generated_at=cert.generated_at,
        error=err,
    )


@router.get(
    "/{certificate_id}/download",
    summary="Download individual certificate PDF",
)
def download_certificate(
    certificate_id: str,
    session: Session = Depends(get_db),
    storage: FileStorage = Depends(get_storage),
) -> FileResponse:
    """Download the generated PDF for an individual certificate."""
    cert = session.query(Certificate).filter(Certificate.id == certificate_id).first()
    if not cert:
        raise NotFoundError("CERTIFICATE_NOT_FOUND", f"Certificate '{certificate_id}' not found")

    if cert.status == CertificateStatus.PENDING.value:
        raise ConflictError(
            "CERTIFICATE_NOT_READY",
            "Certificate generation is still in progress. Please check back shortly.",
        )

    if cert.status == CertificateStatus.FAILED.value:
        raise ConflictError(
            "CERTIFICATE_FAILED",
            f"Certificate generation failed: {cert.error_message or 'Unknown error'}",
        )

    if not cert.file_path or not storage.exists(cert.file_path):
        logger.error(
            "Certificate %s marked success but file '%s' is missing on disk",
            cert.id,
            cert.file_path,
        )
        raise NotFoundError(
            "FILE_MISSING",
            "Certificate file is missing from storage.",
        )

    full_path = storage.get_path(cert.file_path)
    filename = f"{cert.certificate_number or cert.id}.pdf"

    return FileResponse(
        path=full_path,
        media_type="application/pdf",
        filename=filename,
    )
