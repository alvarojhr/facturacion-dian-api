"""Payment terms and instruments, shared by HTTP and core contracts."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PaymentForm = Literal["CONTADO", "CREDITO"]
PaymentMethod = Literal[
    "CASH", "CARD", "CREDIT_CARD", "DEBIT_CARD", "TRANSFER", "CHECK", "CREDIT"
]


class PaymentDetails(BaseModel):
    """Exactly one instrument representation; terms apply to every instrument.

    CARD retains its historical meaning (48, credit card). CREDIT retains code
    30 (credit transfer); neither instrument determines payment_form.
    No instrument amounts are accepted: settlement accounting belongs to the ERP.
    """

    model_config = ConfigDict(json_schema_extra={
        "oneOf": [
            {"required": ["payment_method"], "properties": {
                "payment_method": {"not": {"type": "null"}}, "payment_methods": {"type": "null"},
            }},
            {"required": ["payment_methods"], "properties": {
                "payment_methods": {"not": {"type": "null"}}, "payment_method": {"type": "null"},
            }},
        ],
    })

    payment_method: PaymentMethod | None = Field(
        default=None, description="Legacy single instrument; exclusive with payment_methods"
    )
    payment_methods: list[PaymentMethod] | None = Field(
        default=None, min_length=1,
        description="All payment instruments, in supplied order; exclusive with payment_method. No amounts.",
    )
    payment_form: PaymentForm = "CONTADO"
    payment_due_date: str | None = Field(default=None, description="YYYY-MM-DD; required for CREDITO")

    @model_validator(mode="after")
    def validate_payment_representation(self) -> "PaymentDetails":
        if (self.payment_method is None) == (self.payment_methods is None):
            raise ValueError("Provide exactly one of payment_method or payment_methods")
        if self.payment_due_date is not None:
            if date.fromisoformat(self.payment_due_date).isoformat() != self.payment_due_date:
                raise ValueError("payment_due_date must use YYYY-MM-DD")
        if self.payment_form == "CREDITO" and self.payment_due_date is None:
            raise ValueError("payment_due_date is required for CREDITO")
        return self

    @property
    def resolved_payment_methods(self) -> list[PaymentMethod]:
        if self.payment_methods is not None:
            return self.payment_methods
        assert self.payment_method is not None
        return [self.payment_method]

    def validate_payment_context(self, issue_date: str, document_type: str) -> None:
        if self.payment_due_date and date.fromisoformat(self.payment_due_date) < date.fromisoformat(issue_date):
            raise ValueError("payment_due_date cannot be before issue_date")
        # DEE v1.0, POS-specific DEAN02 (p.110), including POS contingency.
        if document_type.startswith("DOCUMENTO_EQUIVALENTE_POS") and self.payment_form != "CONTADO":
            raise ValueError("POS requires payment_form=CONTADO (DEE DEAN02)")
