from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from threegpp.db import MetadataRepository
from threegpp.documents import DocumentService, FetchPlanner
from threegpp.documents.models import TDocFetchPlan
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
from threegpp.storage import data_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="threegpp", description="Inspect and ingest public 3GPP meeting metadata"
    )
    parser.add_argument("--db", type=Path, default=data_root() / "metadata.duckdb")
    parser.add_argument("--data-dir", type=Path, default=data_root())
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

    plan_fetch = subparsers.add_parser(
        "plan-fetch", help="write an inspectable TDoc body fetch plan"
    )
    plan_fetch.add_argument("--request", required=True, type=Path)
    plan_fetch.add_argument(
        "--minimum-match", choices=["high", "medium", "low"], default="high"
    )
    plan_fetch.add_argument("--organization", action="append")
    plan_fetch.add_argument("--output", required=True, type=Path)
    plan_fetch.add_argument("--batch-limit", type=int, default=50)

    fetch = subparsers.add_parser(
        "fetch-tdocs", help="explicitly fetch and normalize only a saved plan"
    )
    fetch.add_argument("--plan", required=True, type=Path)

    inspect_doc = subparsers.add_parser(
        "inspect-document", help="retrieve a locally normalized TDoc"
    )
    inspect_doc.add_argument("--tdoc", required=True)
    inspect_doc.add_argument("--wg", choices=[item.value for item in WorkingGroup])
    inspect_doc.add_argument("--meeting")

    index_docs = subparsers.add_parser(
        "index-documents", help="index already-normalized TDocs (never downloads)"
    )
    index_docs.add_argument("--wg", choices=[item.value for item in WorkingGroup])
    index_docs.add_argument("--meeting", type=normalize_meeting_identifier)
    index_docs.add_argument("--tdoc")

    search = subparsers.add_parser(
        "search-evidence", help="find lexically relevant normalized evidence blocks"
    )
    _add_search_arguments(search)
    search_tdocs = subparsers.add_parser(
        "search-tdocs", help="aggregate lexical block hits by TDoc"
    )
    _add_search_arguments(search_tdocs)

    extract_evidence = subparsers.add_parser(
        "extract-evidence", help="extract explicit semantic evidence from normalized TDocs"
    )
    _add_evidence_scope_arguments(extract_evidence)
    list_evidence = subparsers.add_parser(
        "list-evidence", help="query persisted explicit semantic evidence"
    )
    _add_evidence_scope_arguments(list_evidence, query_filters=True)
    inspect_evidence = subparsers.add_parser(
        "inspect-evidence", help="resolve one semantic evidence item and its source blocks"
    )
    inspect_evidence.add_argument("--evidence-id", required=True)
    return parser


def _add_wg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--wg", required=True, choices=[item.value for item in WorkingGroup])


def _add_wg_meeting(parser: argparse.ArgumentParser) -> None:
    _add_wg(parser)
    parser.add_argument("--meeting", required=True, type=normalize_meeting_identifier)


def _add_search_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", required=True)
    parser.add_argument("--wg", action="append", choices=[item.value for item in WorkingGroup])
    parser.add_argument("--meeting", action="append", type=normalize_meeting_identifier)
    parser.add_argument("--tdoc", action="append")
    parser.add_argument("--organization", action="append")
    parser.add_argument("--block-type", action="append")
    parser.add_argument("--limit", type=int, default=20)


def _add_evidence_scope_arguments(
    parser: argparse.ArgumentParser, *, query_filters: bool = False
) -> None:
    from threegpp.models import DocumentRole, EvidenceKind, EvidenceScope

    parser.add_argument("--wg", action="append", choices=[item.value for item in WorkingGroup])
    parser.add_argument("--meeting", action="append", type=normalize_meeting_identifier)
    parser.add_argument("--tdoc", action="append")
    parser.add_argument("--document-role", action="append", choices=[item.value for item in DocumentRole])
    if query_filters:
        parser.add_argument("--kind", action="append", choices=[item.value for item in EvidenceKind])
        parser.add_argument("--scope", action="append", choices=[item.value for item in EvidenceScope])
        parser.add_argument("--organization", action="append")
        parser.add_argument("--limit", type=int, default=100)


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
    if args.command in {"extract-evidence", "list-evidence", "inspect-evidence"}:
        from threegpp.evidence import EvidenceExtractionService
        from threegpp.models import EvidenceExtractionRequest

        with MetadataRepository(args.db) as repository:
            service = EvidenceExtractionService(repository, args.data_dir)
            if args.command == "inspect-evidence":
                evidence, blocks = service.get_evidence_sources(args.evidence_id)
                _json({
                    "evidence": evidence.model_dump(mode="json"),
                    "source_blocks": blocks,
                })
                return 0
            request = EvidenceExtractionRequest(
                working_groups=args.wg or [], meetings=args.meeting or [],
                tdoc_ids=args.tdoc or [], document_roles=args.document_role or [],
                evidence_kinds=getattr(args, "kind", None) or [],
                scopes=getattr(args, "scope", None) or [],
                organizations=getattr(args, "organization", None) or [],
                limit=getattr(args, "limit", 100),
            )
            result = (
                service.extract_documents(request) if args.command == "extract-evidence"
                else service.list_evidence(request)
            )
            _json(result)
        return 0

    if args.command == "index-documents":
        from threegpp.documents.models import DocumentReceipt
        from threegpp.search import EvidenceSearchService

        with MetadataRepository(args.db) as repository:
            clauses, values = ["1=1"], []
            for column, value in (("working_group", args.wg), ("meeting_number", args.meeting), ("tdoc_id", args.tdoc)):
                if value:
                    clauses.append(f"{column} = ?"); values.append(value)
            rows = repository.connection.execute(
                "SELECT receipt_json FROM tdoc_documents WHERE " + " AND ".join(clauses)
                + " ORDER BY working_group,meeting_number,tdoc_id", values
            ).fetchall()
            service = EvidenceSearchService(repository, args.data_dir)
            _json([service.index_document(DocumentReceipt.model_validate_json(row[0])) for row in rows])
        return 0

    if args.command in {"search-evidence", "search-tdocs"}:
        from threegpp.models import EvidenceSearchQuery
        from threegpp.search import EvidenceSearchService

        query = EvidenceSearchQuery(query=args.query, working_groups=args.wg or [],
            meetings=args.meeting or [], tdoc_ids=args.tdoc or [],
            organizations=args.organization or [], block_types=args.block_type or [], limit=args.limit)
        with MetadataRepository(args.db) as repository:
            service = EvidenceSearchService(repository, args.data_dir)
            result = service.search_evidence(query) if args.command == "search-evidence" else service.search_tdocs(query)
            _json(result)
        return 0
    if args.command == "plan-fetch":
        from threegpp.models import MatchLevel

        request = StudyRequest.from_yaml(args.request)
        with MetadataRepository(args.db) as repository:
            inventory = StudyService(repository).candidate_inventory(request)
            plan = FetchPlanner(repository, batch_limit=args.batch_limit).from_inventory(
                inventory,
                minimum_match=MatchLevel(args.minimum_match),
                organizations=args.organization,
            )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        plan.to_yaml(args.output)
        _json(
            {
                "plan": str(args.output),
                "pre_download": True,
                "selected": len(plan.items),
                "items": [item.model_dump(mode="json") for item in plan.items],
            }
        )
        return 0

    if args.command == "fetch-tdocs":
        plan = TDocFetchPlan.from_yaml(args.plan)
        with MetadataRepository(args.db) as repository:
            service = DocumentService(repository, args.data_dir)
            preflight = service.preflight(plan)
            outcomes = service.execute(plan)
            _json(
                {
                    "preflight": preflight,
                    "outcomes": [item.model_dump(mode="json") for item in outcomes],
                }
            )
        return 0

    if args.command == "inspect-document":
        with MetadataRepository(args.db) as repository:
            metadata, receipt, blocks, text = DocumentService(
                repository, args.data_dir
            ).retrieve(args.tdoc, args.wg, args.meeting)
            _json(
                {
                    "metadata": metadata.model_dump(mode="json") if metadata else None,
                    "receipt": receipt.model_dump(mode="json"),
                    "blocks": blocks,
                    "normalized_text": text,
                }
            )
        return 0
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
