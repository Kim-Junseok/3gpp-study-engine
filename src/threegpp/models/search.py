from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .meeting import WorkingGroup, normalize_meeting_identifier


class MatchKind(StrEnum):
    EXACT_PHRASE = "exact_phrase"
    ALL_TOKENS = "all_tokens"
    PARTIAL_TOKENS = "partial_tokens"


class EvidenceSearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str
    working_groups: list[WorkingGroup] = Field(default_factory=list)
    meetings: list[str] = Field(default_factory=list)
    tdoc_ids: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    block_types: list[str] = Field(default_factory=list)
    extraction_statuses: list[str] = Field(default_factory=list)
    retention_states: list[str] = Field(default_factory=list)
    limit: int = Field(default=20, ge=1, le=1000)

    @field_validator("working_groups", mode="before")
    @classmethod
    def groups(cls, value: object) -> object:
        return [WorkingGroup.parse(item) for item in value or []]

    @field_validator("meetings", mode="before")
    @classmethod
    def meeting_ids(cls, value: object) -> object:
        return [normalize_meeting_identifier(str(item)) for item in value or []]


class EvidenceRef(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    member: str
    block_id: str
    block_type: str
    heading_path: list[str] = Field(default_factory=list)
    page: int | None = None
    sheet: str | None = None


class EvidenceSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: EvidenceRef
    title: str | None = None
    source_organizations: list[str] = Field(default_factory=list)
    score: float
    matched_terms: list[str]
    match_kind: MatchKind
    phrase_match: bool
    score_explanation: dict[str, Any]
    snippet: str


class TDocSearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    best_block: EvidenceSearchHit
    matching_block_count: int
    aggregate_score: float


class IndexOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    status: str
    indexed_blocks: int = 0
    postings: int = 0
    reused: bool = False
