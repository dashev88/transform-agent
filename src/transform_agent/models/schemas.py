"""Pydantic models for the Transform Agent API."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Supported formats
# ---------------------------------------------------------------------------

class Format(str, Enum):
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    YAML = "yaml"
    TOML = "toml"
    HTML = "html"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"
    PDF = "pdf"
    EXCEL = "excel"
    DOCX = "docx"
    BASE64 = "base64"
    URL_ENCODED = "url_encoded"
    HEX = "hex"


# Binary formats that must be base64-encoded in transit
BINARY_FORMATS = {Format.PDF, Format.EXCEL, Format.DOCX}


# ---------------------------------------------------------------------------
# Requests
# ---------------------------------------------------------------------------

class TransformRequest(BaseModel):
    source_format: Format = Field(..., description="Input data format")
    target_format: Format = Field(..., description="Desired output format")
    data: str = Field(
        ...,
        description="Input data as a string (text formats) or base64-encoded string (binary formats like PDF/Excel/DOCX)",
    )
    options: dict | None = Field(
        default=None,
        description="Optional format-specific options: {delimiter, sheet_name, root_tag, indent, ...}",
    )


class BatchTransformRequest(BaseModel):
    transforms: list[TransformRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Up to 50 transform operations",
    )


class SchemaReshapeRequest(BaseModel):
    data: dict | list = Field(..., description="Input JSON data")
    mapping: dict = Field(
        ...,
        description="Mapping spec: {target_key: source_path, ...} using dot-notation or JMESPath",
    )


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------

class TransformResult(BaseModel):
    result: str = Field(..., description="Transformed data (string or base64)")
    source_format: Format
    target_format: Format
    input_size_bytes: int
    output_size_bytes: int
    transform_time_ms: float
    cost_usd: float
    tx_id: str


class BatchTransformResult(BaseModel):
    results: list[TransformResult]
    total_cost_usd: float
    total_transforms: int
    discount_applied: str | None = "10% bulk"


class CapabilityEntry(BaseModel):
    source: Format
    target: Format
    cost_usd: float
    avg_time_ms: float
    description: str


class CapabilitiesResponse(BaseModel):
    agent_name: str = "data-transform-agent"
    version: str = "0.1.0"
    total_conversions: int
    conversions: list[CapabilityEntry]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class ProvisionRequest(BaseModel):
    agent_name: str | None = Field(default=None, description="Optional name of the calling agent")
    agent_url: str | None = Field(default=None, description="Optional callback URL")


class ProvisionResponse(BaseModel):
    api_key: str
    free_requests_remaining: int
    rate_limit_per_minute: int
    message: str


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------

class RevenueResponse(BaseModel):
    total_revenue_usd: float
    total_transactions: int
    revenue_by_transform: dict[str, float]
    revenue_by_hour: dict[str, float]
