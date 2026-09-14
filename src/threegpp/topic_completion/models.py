from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threegpp.completion import TDocEvidenceCompletionResult
from threegpp.documents.models import RetentionState
from threegpp.historical import rules as historical_rules
from threegpp.models import TDocAvailability, WorkingGroup, normalize_meeting_identifier
from threegpp.topics.models import TopicInventoryAssociation


TOPIC_COMPLETION_PLAN_SCHEMA_VERSION = "1"
TOPIC_COMPLETION_RESULT_SCHEMA_VERSION = "1"
TOPIC_COMPLETION_RULESET_VERSION = "bounded-direct-corpus-v1"
DEFAULT_OPERATION_BOUND = 20
MAX_OPERATION_BOUND = 50


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TopicCompletionItemState(StrEnum):
    ALREADY_INSPECTED = "already_inspected"
    ELIGIBLE_FOR_COMPLETION = "eligible_for_completion"
    NOT_DOWNLOADABLE = "not_downloadable"
    METADATA_UNRESOLVED = "metadata_unresolved"
    METADATA_AMBIGUOUS = "metadata_ambiguous"
    NOT_A_CONTRIBUTION = "not_a_contribution"
    DEFERRED_BY_BOUND = "deferred_by_bound"
    EXPLICITLY_EXCLUDED = "explicitly_excluded"


class TopicCompletionExecutionState(StrEnum):
    COMPLETED = "completed"
    REUSED = "reused"
    FAILED = "failed"
    INELIGIBLE = "ineligible"
    NOT_RUN = "not_run"


class TopicCorpusCompletionPlanRequest(Model):
    profile_id: str
    from_meeting: str | None = None
    to_meeting: str | None = None
    chair_note_snapshots: dict[str, str] = Field(default_factory=dict)
    companies: list[str] = Field(default_factory=list)
    meetings: list[str] = Field(default_factory=list)
    tdoc_ids: list[str] = Field(default_factory=list)
    discussion_only: bool = False
    limit: int = Field(default=DEFAULT_OPERATION_BOUND, ge=1, le=MAX_OPERATION_BOUND)
    retention: RetentionState = RetentionState.CACHE

    @model_validator(mode="after")
    def range_pair(self):
        if bool(self.from_meeting) != bool(self.to_meeting):
            raise ValueError("from_meeting and to_meeting must be supplied together")
        return self

    @field_validator("profile_id")
    @classmethod
    def profile_identifier(cls, value):
        if not value.startswith("topic-profile-"):
            raise ValueError("invalid topic profile ID")
        return value

    @field_validator("tdoc_ids")
    @classmethod
    def tdoc_identifiers(cls, values):
        return sorted({"".join(value.split()).replace("_", "-").upper()
                       for value in values})

    @field_validator("companies")
    @classmethod
    def company_filters(cls, values):
        return sorted({" ".join(value.split()) for value in values},
                      key=lambda value: (value.casefold(), value))

    @field_validator("meetings")
    @classmethod
    def meeting_filters(cls, values):
        return sorted({normalize_meeting_identifier(value)
                       for value in values}, key=historical_rules.meeting_order_key)


class TopicCorpusCompletionPlanItem(Model):
    item_id: str
    tdoc_id: str
    organizations: list[str] = Field(default_factory=list)
    metadata_meeting: str | None = None
    discussion_meetings: list[str] = Field(default_factory=list)
    title: str | None = None
    official_url: str | None = None
    availability: TDocAvailability = TDocAvailability.UNKNOWN
    associations: list[TopicInventoryAssociation] = Field(default_factory=list)
    discussion_confirmed: bool = False
    content_inspected: bool = False
    explicit_meeting_outcome_reference: bool = False
    metadata_resolution_state: str
    metadata_candidate_id: str | None = None
    metadata_source_identity: str | None = None
    raw_local_state: str
    retention_state: RetentionState | None = None
    normalization_state: str
    index_state: str
    semantic_evidence_state: str
    semantic_evidence_count: int | None = None
    state: TopicCompletionItemState
    required_stages: list[str] = Field(default_factory=list)
    reason: str
    state_identity: str


class TopicCorpusCompletionPlan(Model):
    schema_version: str = TOPIC_COMPLETION_PLAN_SCHEMA_VERSION
    plan_id: str
    plan_checksum: str
    request: TopicCorpusCompletionPlanRequest
    profile_id: str
    profile_checksum: str
    inventory_id: str
    corpus_scope_checksum: str
    working_group: WorkingGroup
    topic_label: str
    from_meeting: str
    to_meeting: str
    source_identities: list[str]
    profile_revision_ids: list[str]
    items: list[TopicCorpusCompletionPlanItem]
    batches: list[list[str]]
    summary: dict[str, int]
    limitations: list[str]
    versions: dict[str, str]


class TopicCorpusCompletionItemResult(Model):
    tdoc_id: str
    state: TopicCompletionExecutionState
    completion_result: TDocEvidenceCompletionResult | None = None
    content_inspected: bool
    failure: str | None = None
    warning: str | None = None


class TopicCorpusCompletionResult(Model):
    schema_version: str = TOPIC_COMPLETION_RESULT_SCHEMA_VERSION
    result_id: str
    result_checksum: str
    plan_id: str
    requested_tdoc_ids: list[str]
    selected_tdoc_ids: list[str]
    items: list[TopicCorpusCompletionItemResult]
    summary: dict[str, int]
    updated_inventory_id: str | None = None
    systemic_failure: str | None = None
    limitations: list[str]
    provenance: dict[str, Any]
    versions: dict[str, str]
