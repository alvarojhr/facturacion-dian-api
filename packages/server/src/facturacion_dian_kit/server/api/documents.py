"""Document submission endpoints."""

from __future__ import annotations

from facturacion_dian_kit.core.submission import DocumentSubmissionService
from facturacion_dian_kit.server.contracts import (
    AttachedDocumentRequest,
    AttachedDocumentResponse,
    DocumentSubmissionRequest,
    DocumentSubmissionResponse,
)
from facturacion_dian_kit.server.mappers import (
    to_core_attached_document_request,
    to_core_submission_request,
    to_public_attached_document_response,
    to_public_submission_response,
)
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1")
service = DocumentSubmissionService()


@router.post("/documents/submissions", response_model=DocumentSubmissionResponse)
async def submit_document(req: DocumentSubmissionRequest) -> DocumentSubmissionResponse:
    """Submit a DIAN document using the public API contract."""

    core_request = to_core_submission_request(req)
    include_xml_artifact = True if req.submission_options is None else req.submission_options.return_xml_artifact
    result = await service.submit_document(
        core_request,
        include_xml_artifact=include_xml_artifact,
    )
    return to_public_submission_response(result)


@router.get("/documents/submissions/{tracking_id}", response_model=DocumentSubmissionResponse)
async def get_document_status(tracking_id: str) -> DocumentSubmissionResponse:
    """Look up the DIAN status for a previously submitted tracking id."""

    result = await service.get_status(tracking_id)
    return to_public_submission_response(result)


@router.post("/attached-documents", response_model=AttachedDocumentResponse)
async def build_attached_document(req: AttachedDocumentRequest) -> AttachedDocumentResponse:
    """Build a DIAN AttachedDocument ZIP package."""

    result = service.build_attached_document(to_core_attached_document_request(req))
    return to_public_attached_document_response(
        result.xml_filename,
        result.zip_filename,
        result.content_base64,
    )
