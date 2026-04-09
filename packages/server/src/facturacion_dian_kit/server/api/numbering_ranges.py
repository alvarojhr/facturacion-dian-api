"""Authorized numbering range endpoints."""

from __future__ import annotations

from facturacion_dian_kit.core.config import resolve_wsdl_url, settings
from facturacion_dian_kit.core.dian.client import DianClient
from facturacion_dian_kit.core.models import NumberingRangePayload
from facturacion_dian_kit.server.contracts import (
    NumberingRangeLookupRequest,
    NumberingRangeLookupResponse,
)
from facturacion_dian_kit.server.mappers import to_public_numbering_ranges
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/numbering-ranges")


@router.post("/lookup", response_model=NumberingRangeLookupResponse)
async def lookup_numbering_ranges(req: NumberingRangeLookupRequest) -> NumberingRangeLookupResponse:
    """Lookup DIAN numbering ranges for the provided software code."""

    endpoint_url = resolve_wsdl_url(req.environment or settings.dian.environment)
    client = DianClient(endpoint_url=endpoint_url)
    dian_response = await client.get_numbering_range(
        req.account_code,
        req.account_code_t,
        req.software_code,
    )
    ranges = [
        NumberingRangePayload(
            resolution_number=item.resolution_number,
            resolution_date=item.resolution_date,
            prefix=item.prefix,
            from_number=item.from_number,
            to_number=item.to_number,
            valid_date_from=item.valid_date_from,
            valid_date_to=item.valid_date_to,
            technical_key=item.technical_key,
        )
        for item in dian_response.ranges
    ]
    return to_public_numbering_ranges(ranges)
