from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .meeting import WorkingGroup, normalize_meeting_identifier
from .search import EvidenceRef


class EvidenceKind(StrEnum):
    PROPOSAL = "proposal"
    OBSERVATION = "observation"
    AGREEMENT = "agreement"
    CONCLUSION = "conclusion"
    FFS = "ffs"
    DECISION = "decision"


class EvidenceScope(StrEnum):
    CONTRIBUTION = "contribution"
    MEETING = "meeting"


class DocumentRole(StrEnum):
    CONTRIBUTION = "contribution"
    MEETING_REPORT = "meeting_report"
    CHAIR_MATERIAL = "chair_material"
    AGENDA = "agenda"
    UNKNOWN = "unknown"


class DetectionBasis(StrEnum):
    EXPLICIT_LABEL = "explicit_label"
    HEADING_CONTEXT = "heading_context"
    TABLE_LABEL = "table_label"
    EXPLICIT_SENTENCE_CUE = "explicit_sentence_cue"


class DocumentRoleClassification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: DocumentRole
    basis: list[str] = Field(default_factory=list)


class EvidenceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_ref: EvidenceRef
    sequence: int = Field(ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    row_index: int | None = Field(default=None, ge=0)
    cell_index: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_character_span(self) -> EvidenceSpan:
        if (self.char_start is None) != (self.char_end is None):
            raise ValueError("character spans require both start and end")
        if self.char_start is not None and self.char_end < self.char_start:
            raise ValueError("char_end must not precede char_start")
        return self


class SemanticEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    kind: EvidenceKind
    scope: EvidenceScope
    working_group: WorkingGroup
    meeting: str
    tdoc_id: str
    document_role: DocumentRole
    document_role_basis: list[str]
    source_organizations: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceSpan] = Field(min_length=1)
    statement_text: str
    label: str | None = None
    ordinal: int | None = Field(default=None, ge=1)
    detection_basis: DetectionBasis
    matched_cue: str
    rule_id: str
    rule_version: str
    extracted_at: datetime
    normalization_identity: dict[str, Any]
    evidence_schema_version: str

    @model_validator(mode="after")
    def authority_invariants(self) -> SemanticEvidence:
        if self.scope is EvidenceScope.MEETING and self.source_organizations:
            raise ValueError("meeting-scope evidence must not carry company attribution")
        expected_scope = {
            DocumentRole.CONTRIBUTION: EvidenceScope.CONTRIBUTION,
            DocumentRole.MEETING_REPORT: EvidenceScope.MEETING,
        }.get(self.document_role)
        if expected_scope is not None and self.scope is not expected_scope:
            raise ValueError("document role and evidence scope conflict")
        return self


class EvidenceExtractionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    working_groups: list[WorkingGroup] = Field(default_factory=list)
    meetings: list[str] = Field(default_factory=list)
    tdoc_ids: list[str] = Field(default_factory=list)
    document_roles: list[DocumentRole] = Field(default_factory=list)
    evidence_kinds: list[EvidenceKind] = Field(default_factory=list)
    scopes: list[EvidenceScope] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    limit: int = Field(default=100, ge=1, le=5000)

    @field_validator("working_groups", mode="before")
    @classmethod
    def groups(cls, value: object) -> object:
        return [WorkingGroup.parse(item) for item in value or []]

    @field_validator("meetings", mode="before")
    @classmethod
    def meeting_ids(cls, value: object) -> object:
        return [normalize_meeting_identifier(str(item)) for item in value or []]


class EvidenceExtractionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    status: str
    document_role: DocumentRole
    document_role_basis: list[str]
    blocks_scanned: int = 0
    explicit_labels_detected: int = 0
    evidence_extracted: int = 0
    candidates_rejected_by_authority: int = 0
    ambiguous_cues_ignored: int = 0
    reused: bool = False
