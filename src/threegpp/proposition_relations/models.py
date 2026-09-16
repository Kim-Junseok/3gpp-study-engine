from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from threegpp.models import EvidenceKind, EvidenceSpan, WorkingGroup
from threegpp.propositions import AcceptedProposition


PROPOSITION_RELATION_CORPUS_SCHEMA_VERSION = "1"
PROPOSITION_RELATION_PAIR_RULESET_VERSION = "proposition-relations-v1"
PROPOSITION_RELATION_REVIEW_SCHEMA_VERSION = "1"
PROPOSITION_RELATION_SCHEMA_VERSION = "1"
MAX_ELIGIBLE_PAIRS = 5000


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationAuthority(StrEnum):
    RESEARCHER_ANALYSIS = "RESEARCHER_ANALYSIS"


class PropositionRelationDecision(StrEnum):
    EQUIVALENT = "EQUIVALENT"
    OVERLAPPING = "OVERLAPPING"
    DISTINCT = "DISTINCT"
    CONFLICTING = "CONFLICTING"
    NOT_COMPARABLE = "NOT_COMPARABLE"
    DEFER = "DEFER"


class PairReviewState(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    REVIEWED = "REVIEWED"
    DEFERRED = "DEFERRED"


class RelationBasisSpan(Model):
    segment_index: int = Field(ge=0)
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    exact_text: str

    @model_validator(mode="after")
    def valid(self):
        if self.char_end <= self.char_start:
            raise ValueError("char_end must exceed char_start")
        return self


class PropositionRelationBuildRequest(Model):
    proposition_corpus_id: str
    organizations: list[str] = Field(default_factory=list)
    left_organizations: list[str] = Field(default_factory=list)
    right_organizations: list[str] = Field(default_factory=list)
    tdoc_ids: list[str] = Field(default_factory=list)
    meetings: list[str] = Field(default_factory=list)
    evidence_kinds: list[EvidenceKind] = Field(default_factory=list)
    proposition_ids: list[str] = Field(default_factory=list)

    @field_validator("organizations", "left_organizations", "right_organizations",
                     "tdoc_ids", "meetings", "proposition_ids")
    @classmethod
    def canonical_strings(cls, values):
        return sorted({" ".join(value.split()) for value in values if value.strip()},
                      key=lambda value: (value.casefold(), value))

    @field_validator("evidence_kinds")
    @classmethod
    def canonical_kinds(cls, values):
        return sorted(set(values), key=lambda value: value.value)


class PropositionPairCandidate(Model):
    pair_id: str
    relation_corpus_id: str
    left_proposition_id: str
    right_proposition_id: str
    left_organizations: list[str]
    right_organizations: list[str]
    left_tdoc_id: str
    right_tdoc_id: str
    left_meeting: str
    right_meeting: str
    left_evidence_kind: EvidenceKind
    right_evidence_kind: EvidenceKind
    review_state: PairReviewState = PairReviewState.UNREVIEWED
    pair_ruleset_version: str = PROPOSITION_RELATION_PAIR_RULESET_VERSION


class PropositionRelationReview(Model):
    review_id: str
    relation_corpus_id: str
    pair_id: str
    sequence: int = Field(ge=1)
    decision: PropositionRelationDecision
    left_basis: list[RelationBasisSpan]
    right_basis: list[RelationBasisSpan]
    rationale: str | None = None
    supersedes_review_id: str | None = None
    review_schema_version: str = PROPOSITION_RELATION_REVIEW_SCHEMA_VERSION


class AcceptedPropositionRelation(Model):
    relation_id: str
    relation_corpus_id: str
    pair_id: str
    review_id: str
    left_proposition_id: str
    right_proposition_id: str
    decision: PropositionRelationDecision
    left_basis: list[RelationBasisSpan]
    right_basis: list[RelationBasisSpan]
    authority: RelationAuthority = RelationAuthority.RESEARCHER_ANALYSIS
    left_source_review_id: str
    right_source_review_id: str
    left_evidence_refs: list[EvidenceSpan]
    right_evidence_refs: list[EvidenceSpan]
    relation_schema_version: str = PROPOSITION_RELATION_SCHEMA_VERSION
    pair_ruleset_version: str = PROPOSITION_RELATION_PAIR_RULESET_VERSION


class PropositionRelationCorpusManifest(Model):
    schema_version: str = PROPOSITION_RELATION_CORPUS_SCHEMA_VERSION
    relation_corpus_id: str
    corpus_checksum: str
    request: PropositionRelationBuildRequest
    working_group: WorkingGroup
    source_proposition_corpus_id: str
    source_proposition_corpus_checksum: str
    source_profile_id: str
    source_profile_checksum: str
    source_inventory_id: str
    accepted_proposition_count: int
    accepted_proposition_checksum: str
    eligible_pair_count: int
    pair_artifact_checksum: str
    versions: dict[str, str]
    limitations: list[str]


class PropositionRelationCorpus(Model):
    manifest: PropositionRelationCorpusManifest
    source_propositions: list[AcceptedProposition]
    pair_candidates: list[PropositionPairCandidate]
    reviews: list[PropositionRelationReview]
    accepted_relations: list[AcceptedPropositionRelation]
    reviewed_count: int = 0
    deferred_count: int = 0
