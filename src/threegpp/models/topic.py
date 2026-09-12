from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .evidence import EvidenceKind, EvidenceSpan, SemanticEvidence
from .meeting import WorkingGroup, normalize_meeting_identifier
from .search import EvidenceRef, EvidenceSearchHit


class MeetingAuthorityBasis(StrEnum):
    REPORT_TITLE = "report_title"


class MeetingIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    working_group: WorkingGroup
    meeting_id: str
    raw_text: str | None = None


class MeetingAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid")
    discovery_meeting: MeetingIdentity
    authority_meeting: MeetingIdentity | None = None
    basis: MeetingAuthorityBasis | None = None
    rule_id: str | None = None
    ruleset_version: str
    source_tdoc_id: str
    unresolved_reason: str | None = None


class AgreementDisposition(StrEnum):
    STUDY = "study"
    ADOPT = "adopt"
    SELECT = "select"
    ENDORSE = "endorse"
    REUSE = "reuse"
    DEFER = "defer"
    UNCLASSIFIED = "unclassified"


class DispositionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    disposition: AgreementDisposition
    matched_cue: str | None = None
    rule_id: str | None = None
    rule_version: str
    evidence_span: EvidenceSpan


class ContextRole(StrEnum):
    NOTE = "note"
    QUALIFICATION = "qualification"
    CONDITION = "condition"
    EXCEPTION = "exception"
    FFS_CONTEXT = "ffs_context"


class EvidenceContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_ref: EvidenceRef
    role: ContextRole
    detection_basis: str
    rule_id: str
    rule_version: str
    literal_text: str
    relative_order: int


class EvidenceLinkType(StrEnum):
    REFERENCES_TDOC = "references_tdoc"
    ENDORSES_TDOC = "endorses_tdoc"


class EvidenceLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    relationship: EvidenceLinkType
    target_tdoc_id: str
    matched_literal: str
    evidence_span: EvidenceSpan


class TopicStudyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    working_groups: list[WorkingGroup] = Field(default_factory=list)
    authority_meetings: list[str] = Field(default_factory=list)
    discovery_meetings: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    evidence_kinds: list[EvidenceKind] = Field(default_factory=list)
    include_lexical_candidates: bool = True
    include_contribution_evidence: bool = True
    include_meeting_evidence: bool = True
    include_context: bool = True
    limit_per_group: int = Field(default=20, ge=1, le=500)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        return " ".join(value.split())

    @field_validator("authority_meetings", "discovery_meetings", mode="before")
    @classmethod
    def meetings(cls, value: object) -> object:
        return [normalize_meeting_identifier(item) for item in value or []]


class TopicEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence: SemanticEvidence
    meeting_authority: MeetingAuthority
    disposition: DispositionEvidence | None = None
    context: list[EvidenceContext] = Field(default_factory=list)
    explicit_links: list[EvidenceLink] = Field(default_factory=list)


class MeetingTimelineEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    authority_meeting: MeetingIdentity
    events: list[TopicEvidenceItem]


class TopicCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    documents_available: int
    documents_normalized: int
    documents_indexable: int
    documents_semantically_extracted: int
    meeting_reports_available: int
    authority_meetings: list[str]
    unsupported_documents: int
    filters_applied: dict[str, list[str]]
    limitations: list[str]


class TopicEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str
    study_id: str
    topic_query: str
    coverage: TopicCoverage
    lexical_candidates: list[EvidenceSearchHit]
    contribution_evidence: dict[str, list[TopicEvidenceItem]]
    meeting_evidence: list[TopicEvidenceItem]
    meeting_timeline: list[MeetingTimelineEntry]
    unresolved: list[str]
