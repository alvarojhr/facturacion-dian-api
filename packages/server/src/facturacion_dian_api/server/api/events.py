"""RADIAN receiver event endpoints."""

from __future__ import annotations

from typing import Annotated

from facturacion_dian_api.core.events import EventSubmissionService
from facturacion_dian_api.server.contracts import EmitEventRequest, EmitEventResponse
from facturacion_dian_api.server.examples import (
    EMIT_EVENT_OPENAPI_EXAMPLES,
    EMIT_EVENT_RESPONSE_EXAMPLE,
    ERROR_502_EXAMPLE,
    ERROR_503_EXAMPLE,
    ERROR_504_EXAMPLE,
)
from facturacion_dian_api.server.mappers import to_core_event_request, to_public_event_response
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/v1", tags=["Eventos"])
service = EventSubmissionService()


@router.post(
    "/events",
    response_model=EmitEventResponse,
    summary="Emitir evento RADIAN del receptor",
    responses={
        200: {
            "description": "DIAN proceso el evento y devolvio un resultado funcional.",
            "content": {"application/json": {"example": EMIT_EVENT_RESPONSE_EXAMPLE}},
        },
        502: {"description": "Falla upstream o de transporte con DIAN.", "content": {"application/json": {"example": ERROR_502_EXAMPLE}}},
        503: {"description": "Configuracion local o certificado invalido.", "content": {"application/json": {"example": ERROR_503_EXAMPLE}}},
        504: {"description": "Timeout llamando a DIAN.", "content": {"application/json": {"example": ERROR_504_EXAMPLE}}},
    },
)
async def emit_event(
    req: Annotated[
        EmitEventRequest,
        Body(openapi_examples=EMIT_EVENT_OPENAPI_EXAMPLES),
    ],
) -> EmitEventResponse:
    """Register a receiver event (030/031/032/033) before DIAN.

    The endpoint is stateless: it emits exactly the event it is asked for. The
    mandatory DIAN ordering (``030 -> 032 -> (033 | 031)``) and the claim
    window belong to the caller.
    """

    result = await service.emit_event(to_core_event_request(req))
    return to_public_event_response(result)
