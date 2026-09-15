from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from threegpp.models import EvidenceKind, EvidenceScope, EvidenceSpan, WorkingGroup


PROPOSITION_CORPUS_SCHEMA_VERSION = "1"
PROPOSITION_SEGMENTATION_RULESET_VERSION = "proposition-segmentation-v2"
PROPOSITION_REVIEW_SCHEMA_VERSION = "1"
PROPOSITION_SOURCE_UNIT_SCHEMA_VERSION = "1"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SegmentationReason(StrEnum):
    WHOLE_SOURCE_UNIT = "whole_source_unit"
    SENTENCE_BOUNDARY = "sentence_boundary"
    LIST_ITEM = "list_item"
    NUMBERED_ITEM = "numbered_item"
    OPTION_ITEM = "option_item"
    MANUAL_EXACT_SPAN = "manual_exact_span"


class CandidateReviewState(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"
    EXCLUDED = "excluded"
    REPLACED = "replaced"


class PropositionReviewDecision(StrEnum):
    ACCEPT = "accept"
    DEFER = "defer"
    EXCLUDE_NON_PROPOSITION = "exclude_non_proposition"
    REPLACE_WITH_EXACT_SPANS = "replace_with_exact_spans"


class ExactSourceSpan(Model):
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    exact_text: str

    @model_validator(mode="after")
    def valid(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must exceed char_start")
        return self


class PropositionSourceUnit(Model):
    source_unit_id: str
    source_checksum: str
    topic_profile_id: str
    topic_inventory_id: str
    working_group: WorkingGroup
    meeting: str
    tdoc_id: str
    title: str | None = None
    source_organizations: list[str]
    document_members: list[str]
    semantic_evidence_id: str
    evidence_kind: EvidenceKind
    evidence_scope: EvidenceScope
    exact_text: str
    surface_normalized: str
    evidence_refs: list[EvidenceSpan]
    normalization_identity: dict[str, Any]
    document_identity: dict[str, Any]
    normalized_checksum: str | None
    evidence_artifact_checksum: str | None
    surface_duplicate_group_id: str | None = None
    source_unit_schema_version: str = PROPOSITION_SOURCE_UNIT_SCHEMA_VERSION
    source_unit_ruleset_version: str = PROPOSITION_SEGMENTATION_RULESET_VERSION


class AtomicPropositionCandidate(Model):
    candidate_id: str
    candidate_checksum: str
    source_unit_id: str
    ordinal: int = Field(ge=1)
    exact_text: str
    source_spans: list[ExactSourceSpan]
    evidence_refs: list[EvidenceSpan]
    working_group: WorkingGroup
    meeting: str
    tdoc_id: str
    source_organizations: list[str]
    evidence_kind: EvidenceKind
    segmentation_reason: SegmentationReason
    segmentation_rule_version: str = PROPOSITION_SEGMENTATION_RULESET_VERSION
    context_candidate_id: str | None = None
    context_source_unit_id: str | None = None
    review_state: CandidateReviewState = CandidateReviewState.UNREVIEWED


class PropositionReview(Model):
    review_id: str
    corpus_id: str
    candidate_id: str
    source_unit_id: str
    decision: PropositionReviewDecision
    replacement_spans: list[ExactSourceSpan] = Field(default_factory=list)
    researcher_note: str | None = None
    review_schema_version: str = PROPOSITION_REVIEW_SCHEMA_VERSION


class AcceptedProposition(Model):
    proposition_id: str
    corpus_id: str
    review_id: str
    candidate_id: str
    source_unit_id: str
    exact_text_segments: list[str]
    source_spans: list[ExactSourceSpan]
    evidence_refs: list[EvidenceSpan]
    working_group: WorkingGroup
    meeting: str
    tdoc_id: str
    source_organizations: list[str]
    evidence_kind: EvidenceKind
    evidence_scope: EvidenceScope = EvidenceScope.CONTRIBUTION
    review_schema_version: str = PROPOSITION_REVIEW_SCHEMA_VERSION


class PropositionEvidenceGap(Model):
    tdoc_id: str
    meeting: str | None = None
    reason: str


class PropositionTDocAccounting(Model):
    tdoc_id: str
    meeting: str | None = None
    organizations: list[str]
    content_inspected: bool
    source_unit_count: int
    candidate_count: int


class PropositionCorpusBuildRequest(Model):
    profile_id: str
    from_meeting: str | None = None
    to_meeting: str | None = None
    chair_note_snapshots: dict[str, str] = Field(default_factory=dict)
    limit: int = Field(default=100, ge=1, le=5000)

    @model_validator(mode="after")
    def range_pair(self):
        if bool(self.from_meeting) != bool(self.to_meeting):
            raise ValueError("from_meeting and to_meeting must be supplied together")
        return self


class PropositionCorpusManifest(Model):
    schema_version: str = PROPOSITION_CORPUS_SCHEMA_VERSION
    corpus_id: str
    corpus_checksum: str
    request: PropositionCorpusBuildRequest
    profile_id: str
    profile_checksum: str
    inventory_id: str
    working_group: WorkingGroup
    topic_label: str
    from_meeting: str
    to_meeting: str
    source_unit_count: int
    candidate_count: int
    evidence_gaps: list[PropositionEvidenceGap]
    tdoc_accounting: list[PropositionTDocAccounting]
    organization_groups: dict[str, list[str]]
    source_identities: list[str]
    evidence_identities: list[str]
    source_artifact_checksum: str
    candidate_artifact_checksum: str
    versions: dict[str, str]
    limitations: list[str]


class TopicPropositionCorpus(Model):
    manifest: PropositionCorpusManifest
    source_units: list[PropositionSourceUnit]
    candidates: list[AtomicPropositionCandidate]
    reviews: list[PropositionReview]
    accepted_propositions: list[AcceptedProposition]
    stale_review_ids: list[str] = Field(default_factory=list)
    accepted_count: int = 0
    deferred_count: int = 0
    excluded_count: int = 0
