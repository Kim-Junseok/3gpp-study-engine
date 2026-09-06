from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from threegpp.models import (
    Meeting,
    NormalizedOutput,
    SourceArtifact,
    SpreadsheetParseSummary,
    TDocListSnapshot,
    TDocMetadata,
)

from .normalized import NormalizedStore


class MeetingManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "0.2a.3"
    meeting: Meeting
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    download_artifacts: bool = False
    current_snapshot_url: HttpUrl | None = None
    current_snapshot_reason: str | None = None
    meeting_close_snapshot_url: HttpUrl | None = None
    meeting_close_snapshot_reason: str | None = None
    request_selected_snapshot_url: HttpUrl | None = None
    request_selected_snapshot_reason: str | None = None
    tdoc_list_parses: list[SpreadsheetParseSummary] = Field(default_factory=list)
    tdoc_list_snapshots: list[TDocListSnapshot] = Field(default_factory=list)
    current_output: NormalizedOutput | None = None
    migration_information: list[str] = Field(default_factory=list)
    directory_tdoc_count: int = 0
    enriched_tdoc_count: int = 0
    artifacts: list[SourceArtifact] = Field(default_factory=list)
    tdocs: list[TDocMetadata] = Field(default_factory=list, exclude=True)

    @model_validator(mode="before")
    @classmethod
    def migrate_v01_manifest(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        if "created_at" not in migrated and "retrieved_at" in migrated:
            migrated["created_at"] = migrated.pop("retrieved_at")
        if "download_artifacts" not in migrated and "metadata_only" in migrated:
            migrated["download_artifacts"] = not bool(migrated.pop("metadata_only"))
        # V0.2a.1's universal preferred snapshot has no equivalent role without
        # reclassifying source evidence, so retain the artifacts/rows but not the claim.
        migrated.pop("preferred_tdoc_list_url", None)
        migrated.pop("preferred_tdoc_list_reason", None)
        if migrated.get("schema_version") == "0.1":
            migrated["schema_version"] = "0.2a"
        return migrated


class ManifestStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, manifest: MeetingManifest) -> Path:
        timestamp = manifest.created_at.astimezone(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        filename = (
            f"{manifest.meeting.working_group.value.lower()}-"
            f"{manifest.meeting.meeting_number}-{timestamp}.json"
        )
        return self.root / filename

    def write(self, manifest: MeetingManifest) -> Path:
        if manifest.tdocs and manifest.current_output is None:
            raise ValueError("manifest rows require a normalized current-output reference")
        if (
            manifest.current_output is not None
            and manifest.tdocs
            and manifest.current_output.rows != len(manifest.tdocs)
        ):
            raise ValueError("normalized current-output row count does not match runtime rows")
        if any(item.tdocs and item.normalized_output is None for item in manifest.tdoc_list_snapshots):
            raise ValueError("snapshot rows require normalized-output references")
        if any(
            item.normalized_output is not None
            and item.tdocs
            and item.normalized_output.rows != len(item.tdocs)
            for item in manifest.tdoc_list_snapshots
        ):
            raise ValueError("normalized snapshot-output row count does not match runtime rows")
        path = self.path_for(manifest)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump_json(indent=2)
        temporary = path.with_name(f".{path.name}.part")
        temporary.write_text(payload + "\n", encoding="utf-8")
        temporary.replace(path)
        return path

    @staticmethod
    def read(path: Path, *, hydrate: bool = True) -> MeetingManifest:
        manifest = MeetingManifest.model_validate_json(path.read_text(encoding="utf-8"))
        if not hydrate:
            return manifest
        normalized_store = NormalizedStore(path.parent.parent / "normalized")
        snapshots = [
            item.model_copy(
                update={"tdocs": normalized_store.read(item.normalized_output)}
            )
            if item.normalized_output is not None and not item.tdocs
            else item
            for item in manifest.tdoc_list_snapshots
        ]
        tdocs = manifest.tdocs
        if manifest.current_output is not None and not tdocs:
            tdocs = normalized_store.read(manifest.current_output)
        return manifest.model_copy(update={"tdoc_list_snapshots": snapshots, "tdocs": tdocs})

    def migrate(self, path: Path) -> tuple[MeetingManifest, Path]:
        """Explicitly externalize embedded legacy rows; never overwrite the old receipt."""
        legacy = self.read(path, hydrate=False)
        normalized_store = NormalizedStore(self.root.parent / "normalized")
        snapshots: list[TDocListSnapshot] = []
        for snapshot in legacy.tdoc_list_snapshots:
            output = snapshot.normalized_output
            if output is None:
                if snapshot.tdocs or snapshot.row_count == 0:
                    output = normalized_store.write_snapshot(
                        snapshot.working_group,
                        snapshot.meeting,
                        str(snapshot.source_url),
                        snapshot.filename,
                        snapshot.tdocs,
                    )
                elif snapshot.row_count:
                    raise ValueError(
                        f"cannot migrate {snapshot.source_url}: "
                        "snapshot rows are not embedded"
                    )
            snapshots.append(snapshot.model_copy(update={"normalized_output": output}))
        current_output = legacy.current_output
        if current_output is None:
            current_output = normalized_store.write_current(
                legacy.meeting.working_group,
                legacy.meeting.meeting_number,
                legacy.tdocs,
            )
        migrated = legacy.model_copy(
            update={
                "schema_version": "0.2a.3",
                "created_at": datetime.now(UTC),
                "tdoc_list_snapshots": snapshots,
                "current_output": current_output,
                "migration_information": [
                    *legacy.migration_information,
                    f"externalized embedded rows from {path.name}",
                ],
            }
        )
        return migrated, self.write(migrated)
