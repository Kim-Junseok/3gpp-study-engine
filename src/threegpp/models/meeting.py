from __future__ import annotations

import re
from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class WorkingGroup(StrEnum):
    RAN1 = "RAN1"
    RAN2 = "RAN2"

    @classmethod
    def parse(cls, value: str | WorkingGroup) -> WorkingGroup:
        if isinstance(value, cls):
            return value
        try:
            return cls(value.strip().upper())
        except ValueError as exc:
            raise ValueError(f"unsupported working group {value!r}; expected RAN1 or RAN2") from exc


_MEETING_ID = re.compile(r"^(?P<number>[0-9]+)(?P<suffix>bis|-e)?$", re.IGNORECASE)


def normalize_meeting_identifier(value: str | int) -> str:
    """Return an explicit stable identifier while retaining meaningful suffixes."""
    text = str(value).strip()
    match = _MEETING_ID.fullmatch(text)
    if not match:
        raise ValueError(
            f"invalid meeting identifier {value!r}; expected digits with optional 'bis' or '-e'"
        )
    number = str(int(match.group("number")))
    return number + (match.group("suffix") or "").lower()


class Meeting(BaseModel):
    model_config = ConfigDict(extra="forbid")

    working_group: WorkingGroup
    meeting_number: str
    meeting_name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    location: str | None = None
    source_url: HttpUrl

    @field_validator("working_group", mode="before")
    @classmethod
    def normalize_working_group(cls, value: object) -> WorkingGroup:
        return WorkingGroup.parse(str(value))

    @field_validator("meeting_number", mode="before")
    @classmethod
    def normalize_number(cls, value: object) -> str:
        return normalize_meeting_identifier(str(value))

    @model_validator(mode="after")
    def dates_are_ordered(self) -> Meeting:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self

    @property
    def key(self) -> str:
        return f"{self.working_group.value}-{self.meeting_number}"
