from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .document import TDocMetadata
from .meeting import WorkingGroup, normalize_meeting_identifier
from .parse import SpreadsheetParseSummary
from .storage import NormalizedOutput


class SnapshotRole(StrEnum):
    MEETING_CLOSE = "meeting_close"
    CURRENT_CONSOLIDATED = "current_consolidated"
    HISTORICAL = "historical"
    EXPLICIT_USER_SELECTED = "explicit_user_selected"
    UNKNOWN = "unknown"

    # V0.2a.1 source compatibility aliases.
    FINAL = MEETING_CLOSE
    CONSOLIDATED = CURRENT_CONSOLIDATED
    TIMESTAMPED = HISTORICAL


class TDocListSnapshot(BaseModel):
    """One parsed official list, kept independently from the normalized current view."""

    model_config = ConfigDict(extra="forbid")

    source_url: HttpUrl
    working_group: WorkingGroup
    meeting: str
    filename: str | None = None
    checksum: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    roles: list[SnapshotRole] = Field(min_length=1)
    snapshot_timestamp: datetime | None = None
    row_count: int | None = Field(default=None, ge=0)
    parse_summary: SpreadsheetParseSummary | None = None
    parse_error: str | None = None
    normalized_output: NormalizedOutput | None = None
    # Read legacy V0.2a.2 manifests and keep runtime rows, but never serialize
    # them into a new slim manifest.
    tdocs: list[TDocMetadata] = Field(default_factory=list, exclude=True)

    @field_validator("meeting", mode="before")
    @classmethod
    def normalize_meeting(cls, value: object) -> str:
        return normalize_meeting_identifier(str(value))

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, values: list[SnapshotRole]) -> list[SnapshotRole]:
        return list(dict.fromkeys(values))

    @field_validator("checksum")
    @classmethod
    def lowercase_checksum(cls, value: str | None) -> str | None:
        return value.lower() if value else None
