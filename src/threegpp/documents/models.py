from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from threegpp.models import MatchLevel, TDocAvailability, WorkingGroup


NORMALIZED_DOCUMENT_SCHEMA_VERSION = "1"


class RetentionState(StrEnum):
    CACHE = "cache"
    PINNED = "pinned"


class ExtractionStatus(StrEnum):
    NOT_FETCHED = "not_fetched"
    FETCHED = "fetched"
    PARSED = "parsed"
    PARTIALLY_PARSED = "partially_parsed"
    UNSUPPORTED_FORMAT = "unsupported_format"
    TEXT_UNAVAILABLE = "text_unavailable"
    FAILED = "failed"


class FetchPlanItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    source_url: HttpUrl | None
    availability: TDocAvailability
    selection_reasons: list[str] = Field(default_factory=list)
    retention: RetentionState = RetentionState.CACHE


class TDocFetchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "0.2b.1"
    study: str | None = None
    items: list[FetchPlanItem]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    automatic_batch_limit: int = 50

    def to_yaml(self, path: Path) -> None:
        path.write_text(yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False), encoding="utf-8")

    @classmethod
    def from_yaml(cls, path: Path) -> "TDocFetchPlan":
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class RawArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_url: HttpUrl
    local_path: Path
    filename: str
    retrieved_at: datetime
    media_type: str
    byte_size: int
    sha256: str
    retention: RetentionState


class PackageMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    media_type: str
    byte_size: int
    sha256: str
    role: str = "attachment"
    extraction_status: ExtractionStatus = ExtractionStatus.FETCHED
    warnings: list[str] = Field(default_factory=list)


class ContentBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    block_id: str
    type: str
    text: str | None = None
    member_filename: str
    order: int
    page_number: int | None = None
    heading_level: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    rows: list[list[Any]] | None = None
    sheet_name: str | None = None


class NormalizedMember(BaseModel):
    model_config = ConfigDict(extra="forbid")
    member: PackageMember
    parser: str | None = None
    parser_version: str | None = None
    extraction_status: ExtractionStatus
    warnings: list[str] = Field(default_factory=list)
    blocks: list[ContentBlock] = Field(default_factory=list)


class NormalizationIdentity(BaseModel):
    """Inputs that must match exactly before normalized artifacts can be reused."""

    model_config = ConfigDict(extra="forbid")
    raw_sha256: str
    parser_members: dict[str, str]
    normalized_schema_version: str


class NormalizedTDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = NORMALIZED_DOCUMENT_SCHEMA_VERSION
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    raw: RawArtifact
    members: list[NormalizedMember]
    primary_member: str | None = None
    extraction_status: ExtractionStatus
    warnings: list[str] = Field(default_factory=list)
    normalized_text: str
    normalized_at: datetime
    normalized_checksum: str | None = None


class DocumentReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str = "0.2b.1"
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    raw: RawArtifact
    members: list[PackageMember]
    primary_member: str | None
    extraction_status: ExtractionStatus
    parser_versions: dict[str, str]
    normalization_identity: NormalizationIdentity | None = None
    normalized_path: Path | None
    text_path: Path | None
    normalized_checksum: str | None
    text_checksum: str | None = None
    block_count: int
    text_length: int
    warnings: list[str] = Field(default_factory=list)


class FetchOutcome(BaseModel):
    item: FetchPlanItem
    status: ExtractionStatus
    message: str
    receipt: DocumentReceipt | None = None
