from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from threegpp.db import MetadataRepository
from threegpp.models import SourceArtifact, TDocListSnapshot, TDocMetadata, merge_tdoc_metadata
from threegpp.normalize import TDocListParser, infer_snapshot_timestamp, select_snapshot_views
from threegpp.sources import ThreeGPPSource

from .downloader import HTTPDownloader, safe_filename
from .manifest import ManifestStore, MeetingManifest
from .normalized import NormalizedStore


class MeetingIngestor:
    def __init__(
        self,
        source: ThreeGPPSource,
        repository: MetadataRepository,
        manifest_store: ManifestStore,
        raw_root: Path,
        downloader: HTTPDownloader | None = None,
        parser: TDocListParser | None = None,
        normalized_store: NormalizedStore | None = None,
    ) -> None:
        self.source = source
        self.repository = repository
        self.manifest_store = manifest_store
        self.raw_root = raw_root
        self.downloader = downloader
        self.parser = parser or TDocListParser()
        self.normalized_store = normalized_store or NormalizedStore(raw_root.parent / "normalized")

    def ingest(
        self,
        meeting_id: str,
        *,
        download_artifacts: bool = False,
        enrich_tdocs: bool = False,
        explicit_tdoc_list_url: str | None = None,
        preferred_tdoc_list_url: str | None = None,
    ) -> tuple[MeetingManifest, Path]:
        """Discover by default; downloads require an explicit option."""
        meeting = self.source.get_meeting_metadata(meeting_id)
        tdoc_list_artifacts = self.source.get_tdoc_list(meeting.meeting_number)
        artifacts = [
            *self.source.get_agenda(meeting.meeting_number),
            *self.source.get_meeting_report(meeting.meeting_number),
            *tdoc_list_artifacts,
        ]
        directory_tdocs = self.source.list_tdocs(meeting.meeting_number)
        directory_tdoc_count = len(directory_tdocs)
        parse_summaries = []
        snapshots: list[TDocListSnapshot] = []

        should_enrich = enrich_tdocs or download_artifacts
        views = None
        if should_enrich:
            if explicit_tdoc_list_url and preferred_tdoc_list_url:
                raise ValueError("supply only one explicit TDoc-list URL")
            views = select_snapshot_views(
                tdoc_list_artifacts,
                explicit_url=explicit_tdoc_list_url or preferred_tdoc_list_url,
            )

        if download_artifacts:
            self._require_downloader()
            artifacts = [self._download_artifact(item) for item in artifacts]
        elif views is not None:
            self._require_downloader()
            downloaded_lists = {
                str(item.source_url): self._download_artifact(item)
                for item in tdoc_list_artifacts
            }
            artifacts = [
                downloaded_lists.get(str(item.source_url), item)
                for item in artifacts
            ]

        if views is not None:
            for artifact in artifacts:
                url = str(artifact.source_url)
                if url not in views.roles_by_url:
                    continue
                summary = None
                parsed_tdocs: list[TDocMetadata] = []
                parse_error = None
                if artifact.local_path is None:
                    parse_error = "snapshot was not downloaded"
                else:
                    try:
                        parsed = self.parser.parse(artifact.local_path, artifact)
                    except Exception as exc:  # preserve a per-snapshot diagnostic and continue
                        parse_error = f"{type(exc).__name__}: {exc}"
                    else:
                        summary = parsed.summary
                        parsed_tdocs = parsed.tdocs
                        parse_summaries.append(summary)
                snapshot = TDocListSnapshot(
                    source_url=artifact.source_url,
                    working_group=artifact.working_group,
                    meeting=artifact.meeting,
                    filename=artifact.original_filename,
                    checksum=artifact.checksum,
                    roles=views.roles_by_url[url],
                    snapshot_timestamp=infer_snapshot_timestamp(artifact),
                    row_count=summary.mapped_rows if summary else None,
                    parse_summary=summary,
                    parse_error=parse_error,
                    tdocs=parsed_tdocs,
                )
                if summary is not None:
                    output = self.normalized_store.write_snapshot(
                        snapshot.working_group,
                        snapshot.meeting,
                        str(snapshot.source_url),
                        snapshot.filename,
                        snapshot.tdocs,
                    )
                    snapshot = snapshot.model_copy(update={"normalized_output": output})
                snapshots.append(snapshot)
            tdocs = _build_current_tdoc_view(
                directory_tdocs,
                snapshots,
                current_snapshot_url=str(views.current.artifact.source_url),
            )
        else:
            tdocs = directory_tdocs

        current_output = self.normalized_store.write_current(
            meeting.working_group, meeting.meeting_number, tdocs
        )

        current_snapshot = (
            next(
                (
                    item
                    for item in snapshots
                    if str(item.source_url) == str(views.current.artifact.source_url)
                ),
                None,
            )
            if views is not None
            else None
        )

        manifest = MeetingManifest(
            meeting=meeting,
            created_at=datetime.now(UTC),
            download_artifacts=download_artifacts,
            current_snapshot_url=(views.current.artifact.source_url if views else None),
            current_snapshot_reason=(views.current.reason if views else None),
            meeting_close_snapshot_url=(
                views.meeting_close.artifact.source_url
                if views and views.meeting_close
                else None
            ),
            meeting_close_snapshot_reason=(
                views.meeting_close.reason if views and views.meeting_close else None
            ),
            request_selected_snapshot_url=(
                views.request_selected.artifact.source_url
                if views and views.request_selected
                else None
            ),
            request_selected_snapshot_reason=(
                views.request_selected.reason if views and views.request_selected else None
            ),
            tdoc_list_parses=parse_summaries,
            tdoc_list_snapshots=snapshots,
            directory_tdoc_count=directory_tdoc_count,
            enriched_tdoc_count=(current_snapshot.row_count if current_snapshot else 0) or 0,
            artifacts=artifacts,
            current_output=current_output,
            tdocs=tdocs,
        )
        manifest_path = self.manifest_store.write(manifest)
        self.repository.import_manifest(manifest)
        return manifest, manifest_path

    def _require_downloader(self) -> None:
        if self.downloader is None:
            raise ValueError("a downloader is required for explicit artifact retrieval")

    def _download_artifact(self, artifact: SourceArtifact) -> SourceArtifact:
        assert self.downloader is not None
        filename = safe_filename(artifact.original_filename or str(artifact.source_url), "artifact")
        destination = (
            self.raw_root
            / artifact.working_group.value.lower()
            / artifact.meeting
            / artifact.artifact_type.value
            / filename
        )
        result = self.downloader.download(str(artifact.source_url), destination)
        return artifact.model_copy(
            update={
                "local_path": result.path,
                "checksum": result.sha256,
                "retrieved_at": datetime.now(UTC),
            }
        )


def _build_current_tdoc_view(
    directory_records: list[TDocMetadata],
    snapshots: list[TDocListSnapshot],
    *,
    current_snapshot_url: str,
) -> list[TDocMetadata]:
    """Build directory + current-list inventory; other lists only fill missing facts."""
    directory = {item.tdoc_id: item for item in directory_records}
    by_snapshot = {
        str(snapshot.source_url): {item.tdoc_id: item for item in snapshot.tdocs}
        for snapshot in snapshots
    }
    current = by_snapshot.get(current_snapshot_url, {})
    current_ids = set(directory) | set(current)
    supplemental = sorted(
        (item for item in snapshots if str(item.source_url) != current_snapshot_url),
        key=lambda item: (item.snapshot_timestamp or datetime.min, str(item.source_url)),
    )
    result: list[TDocMetadata] = []
    for tdoc_id in sorted(current_ids):
        record = directory.get(tdoc_id)
        for snapshot in supplemental:
            incoming = by_snapshot[str(snapshot.source_url)].get(tdoc_id)
            if incoming is not None:
                record = incoming if record is None else merge_tdoc_metadata(record, incoming)
        incoming = current.get(tdoc_id)
        if incoming is not None:
            record = incoming if record is None else merge_tdoc_metadata(record, incoming)
        if record is not None:
            result.append(record)
    return result
