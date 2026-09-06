from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from threegpp.db import MetadataRepository
from threegpp.ingest import HTTPDownloader, ManifestStore, MeetingIngestor
from threegpp.models import (
    SnapshotRole,
    StudyRequest,
    TDocQuery,
    WorkingGroup,
    normalize_meeting_identifier,
)
from threegpp.normalize import select_snapshot_views
from threegpp.sources import RAN1Source, RAN2Source, SourceError, ThreeGPPSource
from threegpp.study import StudyService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="threegpp", description="Inspect and ingest public 3GPP meeting metadata"
    )
    parser.add_argument("--db", type=Path, default=Path("data/metadata.duckdb"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_meetings = subparsers.add_parser("list-meetings", help="list advertised meetings")
    _add_wg(list_meetings)

    inspect = subparsers.add_parser("inspect-meeting", help="inspect one meeting's public resources")
    _add_wg_meeting(inspect)

    ingest = subparsers.add_parser("ingest-meeting", help="ingest one meeting; discovery-only by default")
    _add_wg_meeting(ingest)
    ingest.add_argument(
        "--download-artifacts",
        action="store_true",
        help="download meeting-level agenda, report, and TDoc-list artifacts (never TDocs)",
    )
    ingest.add_argument(
        "--enrich-tdocs",
        action="store_true",
        help="download and parse all discovered official TDoc-list snapshots",
    )
    ingest.add_argument(
        "--tdoc-list-url",
        help="select an exact discovered snapshot for this request; canonical current is unchanged",
    )

    list_tdocs = subparsers.add_parser("list-tdocs", help="query locally ingested TDoc metadata")
    _add_wg(list_tdocs)
    list_tdocs.add_argument("--meeting", action="append", type=normalize_meeting_identifier)
    list_tdocs.add_argument("--title-contains")
    list_tdocs.add_argument("--organization")
    list_tdocs.add_argument("--agenda-item")
    list_tdocs.add_argument("--status")
    list_tdocs.add_argument("--tdoc-id")

    inventory = subparsers.add_parser(
        "study-inventory", help="build a metadata-only candidate inventory from a StudyRequest YAML"
    )
    inventory.add_argument("--request", required=True, type=Path)
    inventory.add_argument(
        "--view", choices=["canonical-current", "meeting-close"], default="canonical-current"
    )
    inventory.add_argument("--snapshot-url", help="request-scoped exact stored snapshot URL")

    migrate = subparsers.add_parser(
        "migrate-manifest", help="externalize embedded legacy rows into normalized JSONL.gz"
    )
    migrate.add_argument("--manifest", required=True, type=Path)
    return parser


def _add_wg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wg", required=True, choices=[item.value for item in WorkingGroup])


def _add_wg_meeting(parser: argparse.ArgumentParser) -> None:
    _add_wg(parser)
    parser.add_argument("--meeting", required=True, type=normalize_meeting_identifier)


def source_for(value: str) -> ThreeGPPSource:
    working_group = WorkingGroup.parse(value)
    return RAN1Source() if working_group is WorkingGroup.RAN1 else RAN2Source()


def _json(value: Any) -> None:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    elif isinstance(value, list):
        value = [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value]
    print(json.dumps(value, indent=2, ensure_ascii=False))


def run(args: argparse.Namespace) -> int:
    if args.command == "list-tdocs":
        group = WorkingGroup.parse(args.wg)
        query = TDocQuery(
            working_groups=[group],
            meetings={group: args.meeting} if args.meeting else {},
            title_contains=args.title_contains,
            organization=args.organization,
            agenda_item=args.agenda_item,
            status=args.status,
            tdoc_id=args.tdoc_id,
        )
        with MetadataRepository(args.db) as repository:
            _json(repository.query_tdocs(query))
        return 0

    if args.command == "study-inventory":
        request = StudyRequest.from_yaml(args.request)
        with MetadataRepository(args.db) as repository:
            snapshot_url = args.snapshot_url
            if args.view == "meeting-close":
                if snapshot_url:
                    raise ValueError("--view meeting-close and --snapshot-url are mutually exclusive")
                scoped = [
                    (group, meeting)
                    for group, meetings in request.meetings.items()
                    for meeting in meetings
                ]
                if len(scoped) != 1:
                    raise ValueError("meeting-close view requires exactly one requested meeting")
                snapshot = repository.get_snapshot_for_role(
                    scoped[0][0], scoped[0][1], SnapshotRole.MEETING_CLOSE
                )
                if snapshot is None:
                    raise ValueError("no meeting-close snapshot is stored for the requested meeting")
                snapshot_url = str(snapshot.source_url)
            _json(
                StudyService(repository).candidate_inventory(
                    request, snapshot_url=snapshot_url
                )
            )
        return 0

    if args.command == "migrate-manifest":
        store = ManifestStore(args.data_dir / "manifests")
        manifest, path = store.migrate(args.manifest)
        _json(
            {
                "source_manifest": str(args.manifest),
                "migrated_manifest": str(path),
                "schema_version": manifest.schema_version,
                "current_output": manifest.current_output.model_dump(mode="json")
                if manifest.current_output
                else None,
                "snapshot_outputs": len(
                    [
                        item
                        for item in manifest.tdoc_list_snapshots
                        if item.normalized_output is not None
                    ]
                ),
            }
        )
        return 0

    source = source_for(args.wg)
    try:
        if args.command == "list-meetings":
            _json(source.list_meetings())
            return 0
        if args.command == "inspect-meeting":
            meeting = source.get_meeting_metadata(args.meeting)
            tdoc_lists = source.get_tdoc_list(args.meeting)
            views = select_snapshot_views(tdoc_lists) if tdoc_lists else None
            _json(
                {
                    "meeting": meeting.model_dump(mode="json"),
                    "agenda": [item.model_dump(mode="json") for item in source.get_agenda(args.meeting)],
                    "report": [
                        item.model_dump(mode="json")
                        for item in source.get_meeting_report(args.meeting)
                    ],
                    "tdoc_lists": [item.model_dump(mode="json") for item in tdoc_lists],
                    "tdoc_list_snapshot_roles": (
                        {
                            url: [role.value for role in roles]
                            for url, roles in views.roles_by_url.items()
                        }
                        if views
                        else {}
                    ),
                    "current_snapshot": (
                        str(views.current.artifact.source_url) if views else None
                    ),
                    "current_snapshot_reason": views.current.reason if views else None,
                    "meeting_close_snapshot": (
                        str(views.meeting_close.artifact.source_url)
                        if views and views.meeting_close
                        else None
                    ),
                    "request_selected_snapshot": (
                        str(views.request_selected.artifact.source_url)
                        if views and views.request_selected
                        else None
                    ),
                    "tdoc_count": len(source.list_tdocs(args.meeting)),
                }
            )
            return 0
        if args.command == "ingest-meeting":
            with MetadataRepository(args.db) as repository, HTTPDownloader() as downloader:
                ingestor = MeetingIngestor(
                    source,
                    repository,
                    ManifestStore(args.data_dir / "manifests"),
                    args.data_dir / "raw",
                    downloader,
                )
                manifest, path = ingestor.ingest(
                    args.meeting,
                    download_artifacts=args.download_artifacts,
                    enrich_tdocs=args.enrich_tdocs,
                    explicit_tdoc_list_url=args.tdoc_list_url,
                )
                _json(
                    {
                        "meeting": manifest.meeting.key,
                        "download_artifacts": manifest.download_artifacts,
                        "artifacts": len(manifest.artifacts),
                        "tdocs": len(manifest.tdocs),
                        "directory_tdocs": manifest.directory_tdoc_count,
                        "enriched_tdocs": manifest.enriched_tdoc_count,
                        "current_snapshot": (
                            str(manifest.current_snapshot_url)
                            if manifest.current_snapshot_url
                            else None
                        ),
                        "current_snapshot_reason": manifest.current_snapshot_reason,
                        "meeting_close_snapshot": (
                            str(manifest.meeting_close_snapshot_url)
                            if manifest.meeting_close_snapshot_url
                            else None
                        ),
                        "request_selected_snapshot": (
                            str(manifest.request_selected_snapshot_url)
                            if manifest.request_selected_snapshot_url
                            else None
                        ),
                        "canonical_current_modified_by_request_selection": False,
                        "current_output": (
                            manifest.current_output.model_dump(mode="json")
                            if manifest.current_output
                            else None
                        ),
                        "snapshots": [
                            {
                                "filename": item.filename,
                                "source_url": str(item.source_url),
                                "roles": [role.value for role in item.roles],
                                "timestamp": item.snapshot_timestamp.isoformat()
                                if item.snapshot_timestamp
                                else None,
                                "row_count": item.row_count,
                                "checksum": item.checksum,
                                "warnings": item.parse_summary.warnings
                                if item.parse_summary
                                else [],
                                "parse_error": item.parse_error,
                                "normalized_output": (
                                    item.normalized_output.model_dump(mode="json")
                                    if item.normalized_output
                                    else None
                                ),
                            }
                            for item in manifest.tdoc_list_snapshots
                        ],
                        "manifest": str(path),
                        "database": str(args.db),
                    }
                )
            return 0
    finally:
        close = getattr(source, "close", None)
        if close:
            close()
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (SourceError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
