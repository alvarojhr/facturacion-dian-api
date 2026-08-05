"""Document submission endpoints."""

from __future__ import annotations

from typing import Annotated

from facturacion_dian_api.core.submission import DocumentSubmissionService
from facturacion_dian_api.server.contracts import (
    AttachedDocumentRequest,
    AttachedDocumentResponse,
    DocumentSubmissionRequest,
    DocumentSubmissionResponse,
    DownloadByKeyRequest,
    DownloadByKeyResponse,
)
from facturacion_dian_api.server.examples import (
    ATTACHED_DOCUMENT_REQUEST_EXAMPLE,
    ATTACHED_DOCUMENT_RESPONSE_EXAMPLE,
    DOCUMENT_STATUS_ACCEPTED_RESPONSE_EXAMPLE,
    DOCUMENT_STATUS_RESPONSE_EXAMPLE,
    DOCUMENT_SUBMISSION_OPENAPI_EXAMPLES,
    DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE,
    ERROR_502_EXAMPLE,
    ERROR_503_EXAMPLE,
    ERROR_504_EXAMPLE,
)
from facturacion_dian_api.server.mappers import (
    to_core_attached_document_request,
    to_core_submission_request,
    to_public_attached_document_response,
    to_public_submission_response,
)
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/v1", tags=["Documentos"])
service = DocumentSubmissionService()


@router.post(
    "/documents/submissions",
    response_model=DocumentSubmissionResponse,
    summary="Enviar documento electronico",
    responses={
        200: {
            "description": "DIAN proceso la solicitud y devolvio un resultado funcional.",
            "content": {"application/json": {"example": DOCUMENT_SUBMISSION_RESPONSE_EXAMPLE}},
        },
        502: {"description": "Falla upstream o de transporte con DIAN.", "content": {"application/json": {"example": ERROR_502_EXAMPLE}}},
        503: {"description": "Configuracion local o certificado invalido.", "content": {"application/json": {"example": ERROR_503_EXAMPLE}}},
        504: {"description": "Timeout llamando a DIAN.", "content": {"application/json": {"example": ERROR_504_EXAMPLE}}},
    },
)
async def submit_document(
    req: Annotated[
        DocumentSubmissionRequest,
        Body(openapi_examples=DOCUMENT_SUBMISSION_OPENAPI_EXAMPLES),
    ],
) -> DocumentSubmissionResponse:
    """Submit a document through the public high-level DIAN API."""

    core_request = to_core_submission_request(req)
    include_xml_artifact = True if req.submission_options is None else req.submission_options.return_xml_artifact
    result = await service.submit_document(
        core_request,
        include_xml_artifact=include_xml_artifact,
    )
    return to_public_submission_response(result)


@router.get(
    "/documents/submissions/{tracking_id}",
    response_model=DocumentSubmissionResponse,
    summary="Consultar estado por tracking_id",
    responses={
        200: {
            "description": (
                "Estado funcional devuelto por DIAN. Si el documento ya fue procesado, "
                "`document_key` trae el CUFE/CUDE que DIAN reporta y `qr_url` la URL del catalogo."
            ),
            "content": {
                "application/json": {
                    "examples": {
                        "procesado": {
                            "summary": "Documento ya procesado por DIAN",
                            "value": DOCUMENT_STATUS_ACCEPTED_RESPONSE_EXAMPLE,
                        },
                        "no_encontrado": {
                            "summary": "Tracking id desconocido para DIAN",
                            "value": DOCUMENT_STATUS_RESPONSE_EXAMPLE,
                        },
                    }
                }
            },
        },
        502: {"description": "Falla upstream o de transporte con DIAN.", "content": {"application/json": {"example": ERROR_502_EXAMPLE}}},
        504: {"description": "Timeout llamando a DIAN.", "content": {"application/json": {"example": ERROR_504_EXAMPLE}}},
    },
)
async def get_document_status(tracking_id: str) -> DocumentSubmissionResponse:
    """Look up the DIAN status for a previously submitted tracking id."""

    result = await service.get_status(tracking_id)
    return to_public_submission_response(result)


@router.post(
    "/documents/download-by-key",
    response_model=DownloadByKeyResponse,
    summary="Descargar XML por CUFE/CUDE",
    responses={
        200: {"description": "XML descargado o error funcional de DIAN."},
        502: {"description": "Falla upstream con DIAN.", "content": {"application/json": {"example": ERROR_502_EXAMPLE}}},
        504: {"description": "Timeout llamando a DIAN.", "content": {"application/json": {"example": ERROR_504_EXAMPLE}}},
    },
)
async def download_by_key(req: DownloadByKeyRequest) -> DownloadByKeyResponse:
    """Download the signed XML for a document by its CUFE/CUDE."""

    result = await service.download_by_key(req.document_key, environment=req.environment)
    return DownloadByKeyResponse(
        success=result.success,
        document_key=result.document_key,
        xml_base64=result.xml_base64,
        xml_filename=result.xml_filename,
        status=result.status,
        error_message=result.error_message,
        raw_response=result.raw_response,
    )


@router.post(
    "/attached-documents",
    response_model=AttachedDocumentResponse,
    summary="Construir AttachedDocument",
    responses={
        200: {
            "description": "ZIP interoperable listo para envio por correo.",
            "content": {"application/json": {"example": ATTACHED_DOCUMENT_RESPONSE_EXAMPLE}},
        }
    },
)
async def build_attached_document(
    req: Annotated[
        AttachedDocumentRequest,
        Body(openapi_examples={"attached_document": {"value": ATTACHED_DOCUMENT_REQUEST_EXAMPLE}}),
    ],
) -> AttachedDocumentResponse:
    """Build a DIAN AttachedDocument ZIP package."""

    result = service.build_attached_document(to_core_attached_document_request(req))
    return to_public_attached_document_response(
        result.xml_filename,
        result.zip_filename,
        result.content_base64,
    )
