"""Buyer identity and optional fiscal facts shared by HTTP and direct callers.

Unknown fiscal facts remain None. Technical XML defaults belong in serializers.
"""

from __future__ import annotations

FINAL_CONSUMER_ID = "222222222222"
RESPONSIBILITIES = frozenset({"O-13", "O-15", "O-23", "O-47", "R-99-PN"})
TAX_SCHEMES = {"01": "IVA", "04": "INC", "ZA": "IVA e INC", "ZZ": "No aplica"}
NATURAL_PERSON_DOCUMENTS = frozenset({"CC", "CE", "TI", "PASSPORT"})
REQUIRED_RESPONSIBILITY_FAMILIES = frozenset({
    "NOTA_AJUSTE_DEE_CREDITO", "NOTA_AJUSTE_DEE_DEBITO",
})


def validate_responsibilities(value: str | None) -> str | None:
    if value is None:
        return None
    parts = [part.strip().upper() for part in value.split(";")]
    if any(part not in RESPONSIBILITIES for part in parts):
        raise ValueError("Unknown DIAN fiscal responsibility: " + value)
    normalized = ";".join(parts)
    if len(normalized) > 30:
        raise ValueError("DIAN fiscal responsibilities must not exceed 30 characters")
    return normalized


def validate_tax_scheme(code: str | None, name: str | None) -> None:
    if code is None and name is None:
        return
    if code not in TAX_SCHEMES or name != TAX_SCHEMES[code]:
        raise ValueError(
            "Buyer tax_scheme_id and tax_scheme_name require a complete matching pair: "
            "01/IVA, 04/INC, ZA/IVA e INC or ZZ/No aplica"
        )


def resolve_buyer_identity(
    document_type: str | None, number: str | None, name: str, person_type: str | None,
) -> tuple[str, str]:
    if not name.strip():
        raise ValueError("Buyer name must not be blank")
    if number is not None and not number.strip():
        raise ValueError("Buyer document_number must not be blank")
    if (document_type is None and number is None) or number == FINAL_CONSUMER_ID:
        document_type = "FINAL_CONSUMER"
    if document_type == "FINAL_CONSUMER":
        if number not in (None, FINAL_CONSUMER_ID):
            raise ValueError("FINAL_CONSUMER requires document_number 222222222222 or omission")
        if person_type not in (None, "2"):
            raise ValueError("FINAL_CONSUMER requires additional_account_id 2")
        return "FINAL_CONSUMER", "2"
    if not document_type or not number:
        raise ValueError("Identified buyer requires document_type and document_number")
    if document_type in NATURAL_PERSON_DOCUMENTS:
        if person_type not in (None, "2"):
            raise ValueError("Natural-person document requires additional_account_id 2")
        return document_type, "2"
    if document_type != "NIT" or person_type not in ("1", "2"):
        raise ValueError("NIT buyer requires confirmed additional_account_id (1 or 2)")
    return document_type, person_type


def validate_buyer_family(
    family: str, document_type: str, responsibility: str | None,
) -> None:
    # DEE 1.0 NAAK26 / NADAK26 are 1..1, unlike FE 1.9 CAK26 / DAK26.
    if (family in REQUIRED_RESPONSIBILITY_FAMILIES
            and document_type != "FINAL_CONSUMER" and responsibility is None):
        raise ValueError(
            f"{family} requires known buyer tax_level_code (DEE NAAK26/NADAK26); "
            "unknown responsibilities cannot be replaced with R-99-PN"
        )
