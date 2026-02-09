"""
Pydantic models for charity profile and PDF documents.

This module defines the complete output schema for the smart crawler.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl


class PDFDocumentReference(BaseModel):
    """Metadata for discovered PDF document."""

    id: int | None = None  # Set after DB insertion
    charity_id: int

    document_type: Literal["annual_report", "financial_statement", "impact_report", "form_990", "other"]
    fiscal_year: int | None = None
    title: str | None = None

    source_url: HttpUrl
    source_page_url: HttpUrl | None = None
    anchor_text: str | None = None
    file_path: str | None = None
    file_size_bytes: int | None = None
    file_hash: str | None = None

    page_count: int | None = None
    download_status: Literal["pending", "downloading", "completed", "failed"] = "pending"
    download_date: datetime = Field(default_factory=datetime.utcnow)
    extraction_status: Literal["pending", "in_progress", "completed", "failed"] = "pending"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "charity_id": 123,
                "document_type": "annual_report",
                "fiscal_year": 2023,
                "title": "2023 Annual Report",
                "source_url": "https://charity.org/reports/2023-annual-report.pdf",
                "source_page_url": "https://charity.org/reports",
                "anchor_text": "Download 2023 Annual Report",
                "file_path": "pdfs/123/2023_annual_report.pdf",
                "download_status": "completed",
            }
        }
    )


class CharityProfile(BaseModel):
    """Complete charity profile after multi-source extraction."""

    # Identification
    name: str = Field(..., min_length=1, max_length=255)
    url: HttpUrl
    ein: str | None = Field(None, pattern=r"^\d{2}-?\d{7}$")
    founded_year: int | None = Field(None, ge=1800, le=2100)
    logo_url: HttpUrl | None = None

    # Contact Information
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    address: str | None = None

    # Online Presence
    social_media: dict[str, str] = Field(default_factory=dict)
    donate_url: HttpUrl | None = None
    volunteer_url: HttpUrl | None = None

    # Mission & Programs
    mission: str | None = Field(None, max_length=2000)
    vision: str | None = Field(None, max_length=2000)
    tagline: str | None = Field(None, max_length=500)
    values: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)
    target_populations: list[str] = Field(default_factory=list)
    geographic_coverage: list[str] = Field(default_factory=list)

    # Impact
    impact_metrics: dict[str, Any] = Field(default_factory=dict)
    beneficiaries: str | None = None
    additional_info: str | None = None

    # Governance
    leadership: list[dict[str, str]] = Field(default_factory=list)  # [{name, title, role}]
    tax_deductible: bool | None = None

    # Documents
    pdf_documents: list[int] = Field(default_factory=list)  # IDs from pdf_documents table

    # Metadata
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow)
    data_sources: dict[str, str] = Field(default_factory=dict)  # {field_name: extraction_source}

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "Islamic Relief USA",
                "url": "https://irusa.org",
                "ein": "95-4453134",
                "mission": "Provide relief and development in a dignified manner...",
                "programs": ["Emergency Relief", "Orphan Sponsorship", "Water Projects"],
                "data_sources": {
                    "ein": "json-ld",
                    "mission": "llm-about-page",
                    "programs": "llm-programs-page",
                },
            }
        }
    )
