from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from threegpp.models import AgreementDisposition, EvidenceKind, WorkingGroup


TDOC_STUDY_VIEW_SCHEMA_VERSION = "1"


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DiscussionReferenceView(Model):
    meeting: str
    context: str | None = None
    literal_source_context: str | None = None
    chair_note_source: str
    chair_note_ref: dict[str, Any]
    graph_id: str
    link_id: str
    backend_link_kind: str


class DiscussionView(Model):
    referenced_in_selected_chair_note: bool
    references: list[DiscussionReferenceView] = Field(default_factory=list)
    limitation: str | None = None


class ContributionEvidenceView(Model):
    kind: EvidenceKind
    statement_text: str
    evidence_id: str
    evidence_refs: list[dict[str, Any]]


class ContributionView(Model):
    content_inspected: bool
    evidence: list[ContributionEvidenceView] = Field(default_factory=list)
    limitation: str | None = None


class MeetingOutcomeEvidenceView(Model):
    outcome_type: EvidenceKind
    disposition: AgreementDisposition | None = None
    meeting: str | None = None
    discovery_meeting: str | None = None
    statement_text: str
    literal_reference: str
    evidence_id: str
    evidence_refs: list[dict[str, Any]]
    graph_id: str
    link_id: str
    backend_link_kind: str


class MeetingOutcomeView(Model):
    explicit_tdoc_reference_found: bool
    outcomes: list[MeetingOutcomeEvidenceView] = Field(default_factory=list)
    limitation: str | None = None


class TDocStudyView(Model):
    schema_version: str = TDOC_STUDY_VIEW_SCHEMA_VERSION
    view_id: str
    tdoc_id: str
    working_group: WorkingGroup
    metadata_meeting: str | None = None
    title: str | None = None
    organizations: list[str] = Field(default_factory=list)
    official_url: str | None = None
    discussion: DiscussionView
    contribution: ContributionView
    meeting_outcome: MeetingOutcomeView
    backend_statuses: list[dict[str, Any]] = Field(default_factory=list)
