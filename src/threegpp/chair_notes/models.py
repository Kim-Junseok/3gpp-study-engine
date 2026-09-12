from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from threegpp.documents.models import ExtractionStatus, NormalizationIdentity
from threegpp.models import TDocAvailability, TDocMetadata, WorkingGroup, normalize_meeting_identifier
from threegpp.search import tokenize


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MeetingScope(Model):
    working_group: WorkingGroup
    meeting: str

    @field_validator("meeting", mode="before")
    @classmethod
    def normalize_meeting(cls, value):
        return normalize_meeting_identifier(value)


class ChairNoteSnapshotRole(StrEnum):
    EXPLICIT_FINAL = "explicit_final"
    EOM = "eom"
    INTERMEDIATE = "intermediate"
    UNKNOWN = "unknown"


class ChairNoteArtifact(MeetingScope):
    artifact_id: str
    official_url: HttpUrl
    official_filename: str
    source_directory: HttpUrl
    discovered_at: datetime
    discovery_ruleset: str


class ChairNoteSnapshot(Model):
    schema_version: str
    artifact: ChairNoteArtifact
    snapshot_id: str
    snapshot_label_raw: str | None
    role: ChairNoteSnapshotRole
    role_basis: str
    snapshot_ruleset: str
    raw_filename: str
    raw_path: str | None = None
    raw_sha256: str | None = None
    retrieved_at: datetime | None = None
    normalization_identity: NormalizationIdentity | None = None
    normalization_id: str | None = None
    normalized_path: str | None = None
    normalized_checksum: str | None = None
    extraction_status: ExtractionStatus = ExtractionStatus.NOT_FETCHED
    block_count: int = 0
    tdoc_reference_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class SnapshotSelection(Model):
    selected_snapshot: ChairNoteSnapshot | None
    selection_basis: str
    available_snapshots: list[ChairNoteSnapshot]


class ChairNoteRef(MeetingScope):
    snapshot_id: str
    normalization_id: str
    normalized_checksum: str
    member: str
    block_id: str
    block_type: str
    heading_path: list[str] = Field(default_factory=list)
    page: int | None = None
    sheet: str | None = None
    row_index: int | None = Field(default=None, ge=0)
    cell_index: int | None = Field(default=None, ge=0)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)


class TopicAnchor(Model):
    source_ref: ChairNoteRef
    literal_text: str
    matched_terms: list[str]


class TDocReference(Model):
    tdoc_id: str
    raw_reference: str
    source_ref: ChairNoteRef
    rule_id: str
    ruleset_version: str


class AssociationBasis(StrEnum):
    SAME_BLOCK = "same_block"
    SAME_TABLE_ROW = "same_table_row"
    SAME_DISCUSSION_SECTION = "same_discussion_section"


class DiscussionSection(MeetingScope):
    snapshot_id: str
    section_id: str
    heading_path: list[str]
    topic_anchors: list[TopicAnchor]
    start_ref: ChairNoteRef
    end_ref: ChairNoteRef
    block_count: int
    referenced_tdoc_ids: list[str]


class DiscussionRecord(Model):
    record_id: str
    section_id: str
    topic_anchor: TopicAnchor
    reference: TDocReference
    association_basis: AssociationBasis
    rule_id: str
    ruleset_version: str


class DiscussionCoverageState(StrEnum):
    CHAIR_NOTE_CONFIRMED = "chair_note_confirmed"
    METADATA_RELEVANT_ONLY = "metadata_relevant_only"
    UNKNOWN = "unknown"


class ReferenceResolutionState(StrEnum):
    CURRENT_MEETING_METADATA = "current_meeting_metadata"
    OTHER_KNOWN_METADATA = "other_known_metadata"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class LocalBodyState(Model):
    raw_present: bool = False
    raw_verified: bool = False
    normalized: bool = False
    extraction_status: str | None = None
    indexed_status: str | None = None
    semantic_status: str | None = None


class CoverageTDoc(Model):
    tdoc_id: str
    coverage_state: DiscussionCoverageState
    resolution_state: ReferenceResolutionState
    metadata: TDocMetadata | None = None
    metadata_candidates: list[TDocMetadata] = Field(default_factory=list)
    availability: TDocAvailability | None = None
    local_state: LocalBodyState = Field(default_factory=LocalBodyState)
    associations: list[DiscussionRecord] = Field(default_factory=list)


class DiscussionCoverageRequest(MeetingScope):
    query: str = Field(min_length=1)
    chair_note_snapshot: str | None = None
    include_metadata_candidates: bool = True
    limit: int = Field(default=100, ge=1, le=1000)

    @field_validator("query")
    @classmethod
    def clean_query(cls, value):
        value = " ".join(value.split())
        if not tokenize(value):
            raise ValueError("query must contain searchable tokens")
        return value


class TopicDiscussionCoverage(Model):
    coverage_id: str
    request: DiscussionCoverageRequest
    selection: SnapshotSelection
    matched_sections: list[DiscussionSection]
    chair_note_confirmed: list[CoverageTDoc]
    metadata_relevant_only: list[CoverageTDoc]
    unresolved_references: list[CoverageTDoc]
    diagnostics: dict[str, int]
    versions: dict[str, str]
    limitations: list[str]


class CorpusExpansionItem(Model):
    candidate: CoverageTDoc
    fetch_needed: bool | None
    fetch_eligible: bool
    fetch_reason: str


class TopicCorpusExpansionPlan(Model):
    schema_version: str
    plan_id: str
    coverage: TopicDiscussionCoverage
    items: list[CorpusExpansionItem]
    automatic_batch_limit: int
