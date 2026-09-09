from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threegpp.chair_notes.models import (
    DiscussionRecord, LocalBodyState, TopicDiscussionCoverage,
)
from threegpp.models import SnapshotRole, TDocAvailability, TDocListSnapshot, TDocMetadata, WorkingGroup
from threegpp.search import tokenize

from . import rules


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MeetingAlias(Model):
    working_group: WorkingGroup
    meeting: str
    raw_text: str
    source_alias: str | None
    ruleset_version: str = rules.MEETING_ALIAS_RULESET_VERSION


class HistoricalResolutionState(StrEnum):
    CURRENT_MEETING_METADATA = "current_meeting_metadata"
    OTHER_KNOWN_METADATA = "other_known_metadata"
    HISTORICAL_METADATA = "historical_metadata"
    LISTED_ONLY = "listed_only"
    UNKNOWN = "unknown"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class HistoricalMetadataCandidate(Model):
    candidate_id: str
    metadata: TDocMetadata
    source_layer: str
    snapshot_id: str | None = None
    snapshot_url: str | None = None
    snapshot_filename: str | None = None
    snapshot_checksum: str | None = None
    snapshot_roles: list[SnapshotRole] = Field(default_factory=list)
    snapshot_timestamp: datetime | None = None


class HistoricalMetadataResolution(Model):
    tdoc_id: str
    working_group: WorkingGroup
    discussion_meeting: str | None
    expected_metadata_meeting: str | None
    state: HistoricalResolutionState
    selected: HistoricalMetadataCandidate | None = None
    candidates: list[HistoricalMetadataCandidate] = Field(default_factory=list)
    resolution_basis: str
    resolver_version: str = rules.HISTORICAL_METADATA_RESOLVER_VERSION


class HistoricalCoverageRequest(Model):
    working_group: WorkingGroup
    from_meeting: str
    to_meeting: str
    from_meeting_raw: str | None = None
    to_meeting_raw: str | None = None
    query: str = Field(min_length=1)
    chair_note_snapshots: dict[str, str] = Field(default_factory=dict)
    include_metadata_candidates: bool = True
    limit_per_meeting: int = Field(default=100, ge=1, le=1000)
    max_meetings: int = Field(default=rules.DEFAULT_MAX_MEETINGS, ge=1, le=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_scope(cls, value):
        data = dict(value)
        group = WorkingGroup.parse(data["working_group"])
        data["working_group"] = group
        if not data.get("from_meeting_raw"):
            data["from_meeting_raw"] = str(data["from_meeting"])
        if not data.get("to_meeting_raw"):
            data["to_meeting_raw"] = str(data["to_meeting"])
        data["from_meeting"] = rules.normalize_historical_meeting(data["from_meeting"], group)[0]
        data["to_meeting"] = rules.normalize_historical_meeting(data["to_meeting"], group)[0]
        if rules.normalize_historical_meeting(data["from_meeting_raw"], group)[0] != data["from_meeting"]:
            raise ValueError("from_meeting_raw does not identify from_meeting")
        if rules.normalize_historical_meeting(data["to_meeting_raw"], group)[0] != data["to_meeting"]:
            raise ValueError("to_meeting_raw does not identify to_meeting")
        if rules.meeting_order_key(data["from_meeting"]) > rules.meeting_order_key(data["to_meeting"]):
            raise ValueError("from-meeting must not follow to-meeting")
        snapshots = {}
        for meeting, snapshot in data.get("chair_note_snapshots", {}).items():
            snapshots[rules.normalize_historical_meeting(meeting, group)[0]] = snapshot
        data["chair_note_snapshots"] = snapshots
        return data

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        value = " ".join(value.split())
        if not tokenize(value):
            raise ValueError("query must contain searchable tokens")
        return value


class MeetingCoverageState(StrEnum):
    AVAILABLE = "available"
    CHAIR_NOTE_UNAVAILABLE = "chair_note_unavailable"
    SNAPSHOT_SELECTION_REQUIRED = "snapshot_selection_required"
    CHAIR_NOTE_NOT_NORMALIZED = "chair_note_not_normalized"


class HistoricalSourceState(StrEnum):
    AVAILABLE = "available"
    SOURCE_MISSING = "source_missing"
    SOURCE_UNAVAILABLE = "source_unavailable"
    SNAPSHOT_SELECTION_REQUIRED = "snapshot_selection_required"


class HistoricalMeetingCoverage(Model):
    meeting: MeetingAlias
    state: MeetingCoverageState
    coverage: TopicDiscussionCoverage
    metadata_source_state: HistoricalSourceState
    metadata_snapshots: list[TDocListSnapshot]
    preferred_metadata_snapshot_url: str | None = None
    historical_resolutions: list[HistoricalMetadataResolution]
    diagnostics: dict[str, int]
    limitations: list[str]


class HistoricalCompleteness(StrEnum):
    COMPLETE_FOR_SELECTED_SOURCES = "complete_for_selected_sources"
    PARTIAL_SOURCE_COVERAGE = "partial_source_coverage"
    SOURCE_PREPARATION_REQUIRED = "source_preparation_required"


class HistoricalTopicCoverage(Model):
    schema_version: str
    coverage_id: str
    request: HistoricalCoverageRequest
    meetings: list[HistoricalMeetingCoverage]
    completeness: HistoricalCompleteness
    diagnostics: dict[str, int]
    versions: dict[str, str]
    limitations: list[str]


class HistoricalDiscussionEdge(Model):
    discussion_meeting: str
    association: DiscussionRecord


class HistoricalCorpusItem(Model):
    tdoc_id: str
    metadata_meeting: str | None
    metadata: TDocMetadata | None
    resolution_state: HistoricalResolutionState
    availability: TDocAvailability | None
    local_state: LocalBodyState
    associations: list[HistoricalDiscussionEdge]
    fetch_needed: bool | None
    fetch_eligible: bool
    fetch_reason: str


class HistoricalCorpusExpansionPlan(Model):
    schema_version: str
    plan_id: str
    coverage: HistoricalTopicCoverage
    items: list[HistoricalCorpusItem]
    batches: list[list[str]]
    automatic_batch_limit: int
