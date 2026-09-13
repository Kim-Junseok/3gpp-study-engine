from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threegpp.historical import rules as historical_rules
from threegpp.models import WorkingGroup
from threegpp.search import tokenize

from . import rules


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class TopicTermState(StrEnum):
    USER_SEED = "user_seed"
    EXACT_VARIANT = "exact_variant"
    SOURCE_CANDIDATE = "source_candidate"
    ACCEPTED_SOURCE_TERM = "accepted_source_term"
    RELATED_ONLY = "related_only"
    REJECTED = "rejected"


class TopicSourceType(StrEnum):
    CHAIR_NOTE = "chair_note"
    METADATA_TITLE = "metadata_title"
    CONTRIBUTION_CONTENT = "contribution_content"
    MEETING_OUTCOME = "meeting_outcome"


class TopicQueryGroup(StrEnum):
    USER_SEED = "user_seed"
    EXACT_VARIANT = "exact_variant"
    ACCEPTED_SOURCE_TERM = "accepted_source_term"
    RELATED_DIAGNOSTIC = "related_diagnostic"


class TopicSourceSelectionPolicy(Model):
    selected_chair_notes: bool = True
    metadata_titles: bool = True
    local_documents: bool = True
    chair_note_snapshots: dict[str, str] = Field(default_factory=dict)


class TopicBootstrapRequest(Model):
    working_group: WorkingGroup
    from_meeting: str
    to_meeting: str
    user_terms: list[str] = Field(min_length=1)
    topic_label: str | None = None
    accepted_source_terms: list[str] = Field(default_factory=list)
    related_terms: list[str] = Field(default_factory=list)
    source_policy: TopicSourceSelectionPolicy = Field(default_factory=TopicSourceSelectionPolicy)
    candidate_limit: int = Field(default=rules.DEFAULT_CANDIDATE_LIMIT, ge=1, le=500)
    max_meetings: int = Field(default=24, ge=1, le=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_scope(cls, value):
        data = dict(value)
        group = WorkingGroup.parse(data["working_group"])
        data["working_group"] = group
        data["from_meeting"] = historical_rules.normalize_historical_meeting(
            data["from_meeting"], group)[0]
        data["to_meeting"] = historical_rules.normalize_historical_meeting(
            data["to_meeting"], group)[0]
        if historical_rules.meeting_order_key(data["from_meeting"]) > historical_rules.meeting_order_key(data["to_meeting"]):
            raise ValueError("from-meeting must not follow to-meeting")
        return data

    @field_validator("user_terms", "accepted_source_terms", "related_terms")
    @classmethod
    def clean_terms(cls, values):
        cleaned = []
        for value in values:
            item = " ".join(value.split())
            if not tokenize(item):
                raise ValueError("topic terms must contain searchable tokens")
            if item not in cleaned:
                cleaned.append(item)
        return cleaned


class TopicTermLocator(Model):
    source_type: TopicSourceType
    working_group: WorkingGroup
    meeting: str
    source_identity: str
    source_file: str | None = None
    member: str | None = None
    block_id: str | None = None
    row_index: int | None = None
    cell_index: int | None = None
    char_start: int
    char_end: int
    associated_tdoc_id: str | None = None
    associated_tdoc_ids: list[str] = Field(default_factory=list)
    associated_organizations: list[str] = Field(default_factory=list)
    source_ref: dict[str, Any] | None = None


class TopicTermOccurrence(Model):
    literal_text: str
    locator: TopicTermLocator


class TopicTerm(Model):
    term_id: str
    literal_text: str
    normalized_term: str
    state: TopicTermState
    seed_terms: list[str] = Field(default_factory=list)
    occurrences: list[TopicTermOccurrence] = Field(default_factory=list)
    source_occurrence_count: int = 0
    meetings: list[str] = Field(default_factory=list)
    meeting_occurrence_counts: dict[str, int] = Field(default_factory=dict)
    source_type_occurrence_counts: dict[str, int] = Field(default_factory=dict)
    candidate_tdoc_ids: list[str] = Field(default_factory=list)
    candidate_organizations: list[str] = Field(default_factory=list)
    earliest_observed_meeting: str | None = None
    latest_observed_meeting: str | None = None
    retrieval_support_score: int = 0
    decision_basis: str


class TopicSourceCoverage(Model):
    meetings_requested: list[str]
    chair_note_meetings_available: list[str] = Field(default_factory=list)
    chair_note_meetings_missing: list[str] = Field(default_factory=list)
    chair_note_meetings_unusable: list[str] = Field(default_factory=list)
    metadata_meetings_available: list[str] = Field(default_factory=list)
    metadata_meetings_missing: list[str] = Field(default_factory=list)
    local_documents_inspected: int = 0
    completeness: str


class TopicBootstrapResult(Model):
    schema_version: str = rules.TOPIC_BOOTSTRAP_SCHEMA_VERSION
    bootstrap_id: str
    request: TopicBootstrapRequest
    terms: list[TopicTerm]
    source_coverage: TopicSourceCoverage
    limitations: list[str]
    versions: dict[str, str]


class TopicTerminologyProfile(Model):
    schema_version: str = rules.TOPIC_PROFILE_SCHEMA_VERSION
    profile_id: str
    profile_checksum: str
    working_group: WorkingGroup
    topic_label: str
    from_meeting: str
    to_meeting: str
    user_terms: list[str]
    terms: list[TopicTerm]
    source_bootstrap_id: str
    source_identities: list[str]
    parent_profile_id: str | None = None
    versions: dict[str, str]


class TopicProfileDecision(Model):
    profile_id: str
    accept: list[str] = Field(default_factory=list)
    related: list[str] = Field(default_factory=list)
    reject: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def disjoint(self):
        groups = [set(map(rules.decision_key, values)) for values in
                  (self.accept, self.related, self.reject)]
        if any(groups[i] & groups[j] for i in range(3) for j in range(i + 1, 3)):
            raise ValueError("a term may have only one profile decision")
        return self


class TopicInventoryAssociation(Model):
    query_group: TopicQueryGroup
    query_term: str
    literal_source_phrase: str
    meeting: str
    association_basis: str
    source_locator: dict[str, Any]


class TopicInventoryTDoc(Model):
    tdoc_id: str
    meeting: str | None = None
    title: str | None = None
    organizations: list[str] = Field(default_factory=list)
    official_url: str | None = None
    chair_note_confirmed: bool = False
    metadata_relevant_only: bool = False
    content_inspected: bool = False
    explicit_meeting_outcome_reference: bool = False
    associations: list[TopicInventoryAssociation] = Field(default_factory=list)


class TopicCompanyInventory(Model):
    organization: str
    tdocs: list[TopicInventoryTDoc]


class TopicProfileInventory(Model):
    schema_version: str = rules.TOPIC_INVENTORY_SCHEMA_VERSION
    inventory_id: str
    profile_id: str
    working_group: WorkingGroup
    topic_label: str
    from_meeting: str
    to_meeting: str
    direct_terms: list[str]
    related_diagnostic_terms: list[str]
    companies: list[TopicCompanyInventory]
    unassigned_tdocs: list[TopicInventoryTDoc]
    new_source_candidates: list[TopicTerm]
    new_related_candidates: list[TopicTerm]
    accepted_terms_found: list[str]
    accepted_terms_not_found: list[str]
    source_completeness: str
    limitations: list[str]
    versions: dict[str, str]
