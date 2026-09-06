from __future__ import annotations

import re
from enum import IntEnum, StrEnum
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)

from .meeting import WorkingGroup, normalize_meeting_identifier


class MetadataLayer(IntEnum):
    DIRECTORY = 1
    TDOC_LIST = 2
    TDOC_CONTENT = 3
    ANALYTICAL_INFERENCE = 4


class MetadataSourceKind(StrEnum):
    DIRECTORY = "directory"
    TDOC_LIST = "tdoc_list"


class TDocAvailability(StrEnum):
    DOWNLOADABLE = "downloadable"
    LISTED_ONLY = "listed_only"
    UNKNOWN = "unknown"


class FieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: MetadataLayer
    source_url: HttpUrl
    source_checksum: str | None = None
    source_column: str | None = None


class TDocMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tdoc_id: str
    working_group: WorkingGroup
    meeting: str
    title: str | None = None
    source_organization_raw: str | None = None
    organizations: list[str] = Field(default_factory=list)
    agenda_item: str | None = None
    revision: str | None = None
    status: str | None = None
    document_type: str | None = None
    document_category: str | None = None
    related_tdoc_ids: list[str] = Field(default_factory=list)
    abstract: str | None = None
    agenda_item_description: str | None = None
    intended_for: str | None = None
    release: str | None = None
    specification: str | None = None
    related_work_item: str | None = None
    directory_present: bool = False
    official_list_present: bool = False
    source_url: HttpUrl | None = None
    local_path: Path | None = None
    metadata_source_kind: MetadataSourceKind = MetadataSourceKind.DIRECTORY
    metadata_source_url: HttpUrl | None = None
    metadata_source_checksum: str | None = None
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    raw_metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_v02a_organization_field(cls, data: object) -> object:
        if not isinstance(data, dict) or "source_organization_raw" in data:
            return data
        migrated = dict(data)
        if "source_organization" in migrated:
            migrated["source_organization_raw"] = migrated.pop("source_organization")
        return migrated

    @model_validator(mode="after")
    def infer_compatibility_flags_from_existing_evidence(self) -> TDocMetadata:
        if self.source_url is not None:
            self.directory_present = True
        if (
            self.metadata_source_kind is MetadataSourceKind.TDOC_LIST
            or self.metadata_source_url is not None
        ):
            self.official_list_present = True
        return self

    @property
    def availability(self) -> TDocAvailability:
        if self.directory_present and self.source_url is not None:
            return TDocAvailability.DOWNLOADABLE
        if self.official_list_present:
            return TDocAvailability.LISTED_ONLY
        return TDocAvailability.UNKNOWN

    @field_validator("tdoc_id")
    @classmethod
    def normalize_tdoc_id(cls, value: str) -> str:
        value = re.sub(r"\s+", "", value.strip().upper()).replace("_", "-")
        if not value:
            raise ValueError("tdoc_id must not be empty")
        return value

    @field_validator("working_group", mode="before")
    @classmethod
    def normalize_working_group(cls, value: object) -> WorkingGroup:
        return WorkingGroup.parse(str(value))

    @field_validator("meeting", mode="before")
    @classmethod
    def normalize_meeting(cls, value: object) -> str:
        return normalize_meeting_identifier(str(value))

    @field_validator("organizations", "related_tdoc_ids")
    @classmethod
    def unique_non_empty(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            cleaned = value.strip()
            key = cleaned.casefold()
            if cleaned and key not in seen:
                seen.add(key)
                result.append(cleaned)
        return result


ENRICHABLE_FIELDS = (
    "title",
    "source_organization_raw",
    "agenda_item",
    "revision",
    "status",
    "document_type",
    "document_category",
    "related_tdoc_ids",
    "abstract",
    "agenda_item_description",
    "intended_for",
    "release",
    "specification",
    "related_work_item",
)


def merge_tdoc_metadata(existing: TDocMetadata, incoming: TDocMetadata) -> TDocMetadata:
    """Merge without allowing null or lower-layer data to erase known values."""
    if (
        existing.tdoc_id,
        existing.working_group,
        existing.meeting,
    ) != (incoming.tdoc_id, incoming.working_group, incoming.meeting):
        raise ValueError("cannot merge TDoc records with different identities")

    updates: dict[str, object] = {}
    provenance = dict(existing.field_provenance)
    for field in ENRICHABLE_FIELDS:
        incoming_value = getattr(incoming, field)
        existing_value = getattr(existing, field)
        if incoming_value in (None, [], ""):
            continue
        incoming_provenance = incoming.field_provenance.get(field)
        existing_provenance = provenance.get(field)
        incoming_rank = incoming_provenance.layer if incoming_provenance else _record_layer(incoming)
        existing_rank = existing_provenance.layer if existing_provenance else _record_layer(existing)
        if existing_value in (None, [], "") or incoming_rank >= existing_rank:
            updates[field] = incoming_value
            if incoming_provenance:
                provenance[field] = incoming_provenance

    if not existing.source_url and incoming.source_url:
        updates["source_url"] = incoming.source_url
    if not existing.local_path and incoming.local_path:
        updates["local_path"] = incoming.local_path
    updates["directory_present"] = existing.directory_present or incoming.directory_present
    updates["official_list_present"] = (
        existing.official_list_present or incoming.official_list_present
    )
    if incoming.metadata_source_kind is MetadataSourceKind.TDOC_LIST:
        updates.update(
            metadata_source_kind=incoming.metadata_source_kind,
            metadata_source_url=incoming.metadata_source_url,
            metadata_source_checksum=incoming.metadata_source_checksum,
        )
    updates["field_provenance"] = provenance
    updates["raw_metadata"] = {**existing.raw_metadata, **incoming.raw_metadata}
    if "source_organization_raw" in updates and incoming.organizations:
        updates["organizations"] = incoming.organizations
    elif not existing.organizations and incoming.organizations:
        updates["organizations"] = incoming.organizations
    return existing.model_copy(update=updates)


def _record_layer(record: TDocMetadata) -> MetadataLayer:
    if record.metadata_source_kind is MetadataSourceKind.TDOC_LIST:
        return MetadataLayer.TDOC_LIST
    return MetadataLayer.DIRECTORY
