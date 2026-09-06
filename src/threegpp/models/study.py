from __future__ import annotations

from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .document import TDocAvailability, TDocMetadata
from .meeting import WorkingGroup, normalize_meeting_identifier
from .snapshot import SnapshotRole


class StudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    working_groups: list[WorkingGroup]
    meetings: dict[WorkingGroup, list[str]]
    topics: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    questions: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("working_groups")
    @classmethod
    def unique_working_groups(cls, values: list[WorkingGroup]) -> list[WorkingGroup]:
        return list(dict.fromkeys(values))

    @field_validator("meetings", mode="before")
    @classmethod
    def normalize_meetings(cls, value: object) -> dict[WorkingGroup, list[str]]:
        if not isinstance(value, dict):
            raise ValueError("meetings must map working groups to meeting identifier lists")
        return {
            WorkingGroup.parse(str(group)): [normalize_meeting_identifier(item) for item in identifiers]
            for group, identifiers in value.items()
        }

    @field_validator("topics", "organizations", "questions")
    @classmethod
    def clean_text_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    @model_validator(mode="after")
    def meeting_groups_are_declared(self) -> StudyRequest:
        undeclared = set(self.meetings) - set(self.working_groups)
        if undeclared:
            names = ", ".join(sorted(item.value for item in undeclared))
            raise ValueError(f"meeting groups must appear in working_groups: {names}")
        return self

    @classmethod
    def from_yaml(cls, path: Path | str) -> StudyRequest:
        with Path(path).open(encoding="utf-8") as handle:
            return cls.model_validate(yaml.safe_load(handle))

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.model_dump(mode="json"), sort_keys=False, allow_unicode=True)


class MatchLevel(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CandidateViewKind(StrEnum):
    CANONICAL_CURRENT = "canonical_current"
    MEETING_CLOSE = "meeting_close"
    HISTORICAL_SNAPSHOT = "historical_snapshot"
    SNAPSHOT = "snapshot"


class CandidateView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: CandidateViewKind = CandidateViewKind.CANONICAL_CURRENT
    snapshot_url: str | None = None
    snapshot_checksum: str | None = None
    snapshot_roles: list[SnapshotRole] = Field(default_factory=list)
    snapshot_timestamp: str | None = None
    request_selected: bool = False
    canonical_current_modified: bool = False


class TopicMatchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    match_level: MatchLevel
    topic_tokens: list[str]
    matched_fields: dict[str, list[str]]
    anchor_fields_matched: dict[str, list[str]]
    supporting_fields_matched: dict[str, list[str]]
    covered_topic_tokens: list[str]


class CandidateTDoc(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tdoc: TDocMetadata
    matched_topic: str | None = None
    match_level: MatchLevel | None = None
    matched_fields: dict[str, list[str]] = Field(default_factory=dict)
    anchor_fields_matched: dict[str, list[str]] = Field(default_factory=dict)
    supporting_fields_matched: dict[str, list[str]] = Field(default_factory=dict)
    covered_topic_tokens: list[str] = Field(default_factory=list)
    topic_matches: list[TopicMatchEvidence] = Field(default_factory=list)
    availability: TDocAvailability


class SnapshotCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = 0
    parsed: int = 0
    current_consolidated: int = 0
    meeting_close: int = 0
    historical: int = 0
    explicit_user_selected: int = 0
    unknown: int = 0


class CandidateInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    study_name: str
    classification: str = "metadata-based candidate discovery; document bodies not analyzed"
    view: CandidateView = Field(default_factory=CandidateView)
    meetings_inspected: dict[str, list[str]]
    missing_meetings: dict[str, list[str]] = Field(default_factory=dict)
    candidate_count: int
    downloadable_count: int
    listed_only_count: int
    unknown_availability_count: int
    high_match_count: int
    medium_match_count: int
    low_match_count: int
    snapshot_coverage: dict[str, SnapshotCoverage] = Field(default_factory=dict)
    by_organization: dict[str, int]
    by_meeting: dict[str, int]
    by_agenda_item: dict[str, int]
    candidate_tdocs: list[CandidateTDoc]
