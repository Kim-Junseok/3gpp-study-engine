from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .meeting import WorkingGroup, normalize_meeting_identifier


class ArtifactType(StrEnum):
    AGENDA = "agenda"
    MEETING_REPORT = "meeting_report"
    TDOC_LIST = "tdoc_list"
    TDOC = "tdoc"


class SourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_type: ArtifactType
    working_group: WorkingGroup
    meeting: str
    source_url: HttpUrl
    discovered_at: datetime
    retrieved_at: datetime | None = None
    original_filename: str | None = None
    local_path: Path | None = None
    checksum: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")

    @model_validator(mode="before")
    @classmethod
    def migrate_v01_timestamps(cls, data: object) -> object:
        """Read V0.1 manifests without claiming metadata-only artifacts were downloaded."""
        if not isinstance(data, dict) or "discovered_at" in data:
            return data
        migrated = dict(data)
        old_timestamp = migrated.get("retrieved_at")
        migrated["discovered_at"] = old_timestamp
        if not migrated.get("local_path") or not migrated.get("checksum"):
            migrated["retrieved_at"] = None
        return migrated

    @model_validator(mode="after")
    def downloaded_fields_are_consistent(self) -> SourceArtifact:
        download_fields = (self.retrieved_at, self.local_path, self.checksum)
        if any(value is not None for value in download_fields) and not all(
            value is not None for value in download_fields
        ):
            raise ValueError("retrieved_at, local_path, and checksum must be set together")
        return self

    @field_validator("working_group", mode="before")
    @classmethod
    def normalize_working_group(cls, value: object) -> WorkingGroup:
        return WorkingGroup.parse(str(value))

    @field_validator("meeting", mode="before")
    @classmethod
    def normalize_meeting(cls, value: object) -> str:
        return normalize_meeting_identifier(str(value))

    @field_validator("checksum")
    @classmethod
    def lowercase_checksum(cls, value: str | None) -> str | None:
        return value.lower() if value else value
