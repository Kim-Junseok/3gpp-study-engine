from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .meeting import WorkingGroup, normalize_meeting_identifier


class TDocQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    working_groups: list[WorkingGroup] = Field(default_factory=list)
    meetings: dict[WorkingGroup, list[str]] = Field(default_factory=dict)
    title_contains: str | None = None
    organization: str | None = None
    agenda_item: str | None = None
    status: str | None = None
    tdoc_id: str | None = None

    @field_validator("meetings", mode="before")
    @classmethod
    def normalize_meetings(cls, value: object) -> dict[WorkingGroup, list[str]]:
        if not isinstance(value, dict):
            raise ValueError("meetings must be a mapping")
        return {
            WorkingGroup.parse(str(group)): [normalize_meeting_identifier(item) for item in identifiers]
            for group, identifiers in value.items()
        }

    @field_validator("title_contains", "organization", "agenda_item", "status", "tdoc_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
