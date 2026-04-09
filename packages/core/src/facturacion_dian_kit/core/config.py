"""Environment-backed configuration for facturacion-dian-kit."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(".env")
WORKING_DIRECTORY = Path.cwd()


class CompanySettings(BaseSettings):
    """Issuer defaults used to build UBL documents."""

    model_config = SettingsConfigDict(
        env_prefix="COMPANY_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    name: str = "Example Issuer SAS"
    nit: str = "900123456"
    dv: str = "7"
    address: str = "Street 10 #20-30"
    city_code: str = "11001"
    city_name: str = "Bogota"
    department_code: str = "11"
    department_name: str = "Bogota D.C."
    country_code: str = "CO"
    phone: str = "3001234567"
    email: str = "billing@example-issuer.test"
    tax_scheme: str = "ZZ"
    economic_activity: str = "4752"


class DianSettings(BaseSettings):
    """DIAN integration settings."""

    model_config = SettingsConfigDict(
        env_prefix="DIAN_",
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["habilitacion", "produccion"] = "habilitacion"
    lookup_environment: Literal["habilitacion", "produccion"] | None = None
    lookup_wsdl_url: str = ""
    cert_path: str = "./certificates/cert.p12"
    cert_password: str = ""
    software_id: str = ""
    software_pin: str = ""
    software_name: str = "Facturacion DIAN Kit"
    software_manufacturer_name: str = ""
    software_manufacturer_company_name: str = ""
    technical_key: str = ""
    test_set_id: str = ""
    resolution_prefix: str = ""
    resolution_number: str = ""
    resolution_range_from: int = 0
    resolution_range_to: int = 0
    resolution_valid_from: str = ""
    resolution_valid_to: str = ""

    @property
    def resolved_cert_path(self) -> Path:
        path = Path(self.cert_path)
        if path.is_absolute():
            return path
        return (WORKING_DIRECTORY / path).resolve()

    @property
    def wsdl_url(self) -> str:
        return resolve_wsdl_url(self.environment)

    @property
    def resolved_lookup_wsdl_url(self) -> str:
        if self.lookup_wsdl_url.strip():
            return self.lookup_wsdl_url.strip()
        return resolve_wsdl_url(self.lookup_environment or self.environment)

    @property
    def catalog_url(self) -> str:
        return "https://catalogo-vpfe.dian.gov.co/document/searchqr?documentkey="

    @property
    def tipo_ambiente(self) -> str:
        return "1" if self.environment == "produccion" else "2"


class RuntimeSettings(BaseSettings):
    """Generic runtime settings shared by local runs and Docker."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    log_level: str = Field(default="info", alias="LOG_LEVEL")


class Settings(BaseSettings):
    """Top-level settings object."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    runtime: RuntimeSettings = Field(default_factory=RuntimeSettings)
    dian: DianSettings = Field(default_factory=DianSettings)
    company: CompanySettings = Field(default_factory=CompanySettings)


settings = Settings()


def resolve_wsdl_url(environment: Literal["habilitacion", "produccion"]) -> str:
    if environment == "produccion":
        return "https://vpfe.dian.gov.co/WcfDianCustomerServices.svc"
    return "https://vpfe-hab.dian.gov.co/WcfDianCustomerServices.svc"
