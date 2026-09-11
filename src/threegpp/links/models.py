from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from threegpp.models import AgreementDisposition, WorkingGroup, normalize_meeting_identifier
from threegpp.models.evidence import DocumentRole, EvidenceKind, EvidenceScope


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceNodeKind(StrEnum):
    TDOC = "tdoc"
    SEMANTIC_EVIDENCE = "semantic_evidence"
    DISCUSSION_RECORD = "discussion_record"
    MEETING = "meeting"


class ExplicitLinkKind(StrEnum):
    SAME_TDOC = "same_tdoc"
    EXPLICIT_TDOC_REFERENCE = "explicit_tdoc_reference"
    EXPLICIT_MEETING_REFERENCE = "explicit_meeting_reference"
    EXPLICIT_REPLY_REFERENCE = "explicit_reply_reference"
    EXPLICIT_REVISION_REFERENCE = "explicit_revision_reference"
    EXPLICIT_SUPERSESSION_REFERENCE = "explicit_supersession_reference"
    DISCUSSION_REFERENCE = "discussion_reference"


class LinkCoverageState(StrEnum):
    SOURCE_AVAILABLE = "source_available"
    SOURCE_MISSING = "source_missing"
    BODY_NOT_LOCAL = "body_not_local"
    SEMANTIC_EVIDENCE_NOT_EXTRACTED = "semantic_evidence_not_extracted"
    NO_EXPLICIT_LINK = "no_explicit_link"
    LINKED = "linked"
    AMBIGUOUS_REFERENCE = "ambiguous_reference"
    UNRESOLVED_REFERENCE = "unresolved_reference"


class LinkCompleteness(StrEnum):
    COMPLETE_FOR_AVAILABLE_EVIDENCE = "complete_for_available_evidence"
    PARTIAL_EVIDENCE_COVERAGE = "partial_evidence_coverage"
    SOURCE_PREPARATION_REQUIRED = "source_preparation_required"


class SourceLocator(Model):
    locator_type: str
    source_artifact: str
    source_identity: str
    reference: dict[str, Any]


class EvidenceNodeRef(Model):
    node_id: str
    kind: EvidenceNodeKind
    working_group: WorkingGroup
    meeting: str | None = None
    meeting_raw: str | None = None
    tdoc_id: str | None = None
    evidence_kind: EvidenceKind | None = None
    evidence_scope: EvidenceScope | None = None
    document_role: DocumentRole | None = None
    source_organizations: list[str] = Field(default_factory=list)
    source_artifact: str
    source_identity: str
    locators: list[SourceLocator] = Field(default_factory=list)

    @field_validator("meeting", mode="before")
    @classmethod
    def normalize_meeting(cls, value):
        return normalize_meeting_identifier(value) if value else None


class ExplicitEvidenceLink(Model):
    link_id: str
    kind: ExplicitLinkKind
    source_node: EvidenceNodeRef
    target_node: EvidenceNodeRef
    literal_basis: str = Field(min_length=1)
    locators: list[SourceLocator] = Field(min_length=1)
    discussion_meeting: str | None = None
    source_meeting: str | None = None
    discovery_meeting: str | None = None
    authority_meeting: str | None = None
    metadata_meeting: str | None = None
    resolution_state: LinkCoverageState
    resolution_candidates: list[EvidenceNodeRef] = Field(default_factory=list)
    disposition: AgreementDisposition | None = None
    confidence: Literal["deterministic_explicit"] = "deterministic_explicit"
    ruleset_version: str

    @field_validator("discussion_meeting", "source_meeting", "discovery_meeting",
                     "authority_meeting", "metadata_meeting", mode="before")
    @classmethod
    def normalize_meetings(cls, value):
        return normalize_meeting_identifier(value) if value else None


class LinkCoverage(Model):
    tdoc_id: str
    working_group: WorkingGroup
    state: LinkCoverageState
    metadata_meeting: str | None = None
    detail: str


class EvidenceLinkGraph(Model):
    schema_version: str
    graph_schema_version: str
    graph_id: str
    graph_checksum: str
    working_group: WorkingGroup
    scope: dict[str, Any]
    nodes: list[EvidenceNodeRef]
    links: list[ExplicitEvidenceLink]
    coverage: list[LinkCoverage]
    completeness: LinkCompleteness
    source_identities: list[str]
    versions: dict[str, str]
    diagnostics: dict[str, int]
    limitations: list[str]


class LinkPreparationItem(Model):
    tdoc_id: str
    meeting: str | None = None
    coverage_state: LinkCoverageState
    body_fetch_needed: bool | None
    normalization_needed: bool
    index_needed: bool
    semantic_extraction_needed: bool
    meeting_evidence_missing: bool
    reason: str


class LinkPreparationPlan(Model):
    schema_version: str
    plan_id: str
    graph_id: str
    items: list[LinkPreparationItem]
    executes_actions: Literal[False] = False
