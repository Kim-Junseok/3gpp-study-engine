from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class NormalizedOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: Path
    rows: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")
    format: Literal["jsonl+gzip"] = "jsonl+gzip"

    @field_validator("sha256")
    @classmethod
    def lowercase_checksum(cls, value: str) -> str:
        return value.lower()
