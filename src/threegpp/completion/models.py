from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from threegpp.documents.models import RetentionState
from threegpp.historical.models import HistoricalMetadataResolution
from threegpp.models import WorkingGroup


COMPLETION_SCHEMA_VERSION = "1"


class CompletionRefreshPolicy(StrEnum):
    IF_STALE = "if_stale"


class CompletionStageState(StrEnum):
    COMPLETED = "completed"
    REUSED = "reused"
    BLOCKED = "blocked"
    FAILED = "failed"
    NOT_RUN = "not_run"


class CompletionFailure(StrEnum):
    METADATA_UNRESOLVED = "metadata_unresolved"
    METADATA_AMBIGUOUS = "metadata_ambiguous"
    NOT_A_CONTRIBUTION = "not_a_contribution"
    BODY_NOT_DOWNLOADABLE = "body_not_downloadable"
    OFFLINE_BODY_MISSING = "offline_body_missing"
    DOWNLOAD_FAILED = "download_failed"
    RAW_CHECKSUM_INVALID = "raw_checksum_invalid"
    NORMALIZATION_FAILED = "normalization_failed"
    INDEX_FAILED = "index_failed"
    SEMANTIC_EXTRACTION_FAILED = "semantic_extraction_failed"
    LINK_REFRESH_FAILED = "link_refresh_failed"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TDocEvidenceCompletionRequest(Model):
    working_group: WorkingGroup
    tdoc_id: str
    retention: RetentionState = RetentionState.CACHE
    refresh_policy: CompletionRefreshPolicy = CompletionRefreshPolicy.IF_STALE
    offline: bool = False
    expected_metadata_meeting: str | None = None
    discussion_meeting: str | None = None

    @field_validator("working_group", mode="before")
    @classmethod
    def group(cls, value):
        return WorkingGroup.parse(value)

    @field_validator("tdoc_id")
    @classmethod
    def identifier(cls, value):
        return "".join(value.split()).replace("_", "-").upper()


class CompletionStageResult(Model):
    state: CompletionStageState
    detail: str
    identity: str | None = None
    values: dict[str, Any] = Field(default_factory=dict)


class TDocEvidenceCompletionResult(Model):
    schema_version: str = COMPLETION_SCHEMA_VERSION
    result_id: str
    request: TDocEvidenceCompletionRequest
    metadata_resolution: HistoricalMetadataResolution
    metadata: CompletionStageResult
    body: CompletionStageResult
    normalization: CompletionStageResult
    index: CompletionStageResult
    semantic_extraction: CompletionStageResult
    link_status: CompletionStageResult
    retention: RetentionState | None = None
    content_inspected: bool = False
    study_view_id: str | None = None
    evidence_count: int | None = None
    failure: CompletionFailure | None = None
    warnings: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
