"""Buyer lookup endpoints."""

from __future__ import annotations

from typing import Annotated

from facturacion_dian_kit.core.config import resolve_wsdl_url, settings
from facturacion_dian_kit.core.dian.client import DianClient
from facturacion_dian_kit.core.models import CustomerLookupPayload
from facturacion_dian_kit.server.contracts import BuyerLookupRequest, BuyerLookupResponse
from facturacion_dian_kit.server.examples import (
    BUYER_LOOKUP_REQUEST_EXAMPLE,
    BUYER_LOOKUP_RESPONSE_EXAMPLE,
    ERROR_502_EXAMPLE,
    ERROR_504_EXAMPLE,
)
from facturacion_dian_kit.server.mappers import to_public_buyer_response
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/v1/customers", tags=["Consultas"])

DOCUMENT_TYPE_TO_DIAN = {
    "NIT": "31",
    "CC": "13",
    "CE": "22",
    "TI": "12",
    "PASSPORT": "41",
}


@router.post(
    "/lookup",
    response_model=BuyerLookupResponse,
    summary="Consultar adquiriente en DIAN",
    responses={
        200: {
            "description": "Respuesta normalizada del adquiriente.",
            "content": {"application/json": {"example": BUYER_LOOKUP_RESPONSE_EXAMPLE}},
        },
        502: {"description": "Falla upstream o de transporte con DIAN.", "content": {"application/json": {"example": ERROR_502_EXAMPLE}}},
        504: {"description": "Timeout llamando a DIAN.", "content": {"application/json": {"example": ERROR_504_EXAMPLE}}},
    },
)
async def lookup_customer(
    req: Annotated[
        BuyerLookupRequest,
        Body(openapi_examples={"buyer_lookup": {"value": BUYER_LOOKUP_REQUEST_EXAMPLE}}),
    ],
) -> BuyerLookupResponse:
    """Lookup buyer data in DIAN using GetAcquirer."""

    endpoint_url = (
        settings.dian.resolved_lookup_wsdl_url
        if req.environment is None
        else resolve_wsdl_url(req.environment)
    )
    client = DianClient(endpoint_url=endpoint_url)
    dian_response = await client.get_acquirer(
        DOCUMENT_TYPE_TO_DIAN[req.document_type],
        req.document_number,
    )

    payload = None
    if dian_response.found and dian_response.receiver_name:
        payload = CustomerLookupPayload(
            display_name=dian_response.receiver_name,
            document_type=req.document_type,
            document_number=req.document_number,
            email=dian_response.receiver_email,
            country_code="CO",
        )

    return to_public_buyer_response(
        found=dian_response.found and payload is not None,
        error_message=None if payload is not None else dian_response.message,
        customer=payload,
    )
