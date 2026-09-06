from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from .document import TDocMetadata


class SpreadsheetParseSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_url: HttpUrl
    sheet_name: str
    header_row: int
    total_data_rows: int
    mapped_rows: int
    unmapped_rows: int
    duplicate_rows: int
    mapped_columns: dict[str, list[str]] = Field(default_factory=dict)
    unknown_columns: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SpreadsheetParseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: SpreadsheetParseSummary
    tdocs: list[TDocMetadata]
