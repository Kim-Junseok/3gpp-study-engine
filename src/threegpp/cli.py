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
    authority = subparsers.add_parser(
        "inspect-meeting-authority", help="resolve discovery and authority meetings for a local TDoc"
    )
    authority.add_argument("--tdoc", required=True)
    topic = subparsers.add_parser(
        "study-topic", help="build an offline, evidence-layered topic bundle (never downloads)"
    )
    topic.add_argument("--query", required=True)
    topic.add_argument("--wg", action="append", choices=[item.value for item in WorkingGroup])
    topic.add_argument("--authority-meeting", action="append", type=normalize_meeting_identifier)
    topic.add_argument("--discovery-meeting", action="append", type=normalize_meeting_identifier)
    topic.add_argument("--organization", action="append")
    from threegpp.models import EvidenceKind
    topic.add_argument("--kind", action="append", choices=[item.value for item in EvidenceKind])
    topic.add_argument("--limit", type=int, default=20)
    for name, help_text in (
        ("discover-chair-notes", "discover Chair Note snapshots; no body downloads"),
        ("fetch-chair-note", "explicitly fetch and normalize one Chair Note snapshot"),
        ("inspect-chair-note", "inspect a local Chair Note snapshot; no downloads"),
        ("discussion-coverage", "find positive Chair Note discussion coverage; no downloads"),
        ("plan-topic-corpus", "plan selective corpus expansion; no body downloads"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        _add_wg_meeting(command)
        if name != "discover-chair-notes":
            command.add_argument("--snapshot", required=name in {"fetch-chair-note", "inspect-chair-note"})
        if name == "fetch-chair-note":
            command.add_argument("--refresh", action="store_true", help="verify remote bytes; checksum conflicts fail")
        if name in {"discussion-coverage", "plan-topic-corpus"}:
            command.add_argument("--query", required=True)
            command.add_argument("--include-metadata-candidates", action=argparse.BooleanOptionalAction, default=True)
            command.add_argument("--limit", type=int, default=100)
        if name == "plan-topic-corpus":
            command.add_argument("--tdoc", action="append", help="explicit selection for an existing-format fetch plan")
            command.add_argument("--fetch-plan", type=Path, help="write selected TDocs as a TDocFetchPlan YAML; never execute it")
    historical_resolve = subparsers.add_parser(
        "historical-metadata-resolve",
        help="resolve a TDoc against canonical-current and stored official historical metadata",
    )
    _add_wg(historical_resolve)
    historical_resolve.add_argument("--tdoc", required=True)
    historical_resolve.add_argument("--meeting", required=True,
                                    help="expected historical metadata meeting; aliases are accepted")
    historical_resolve.add_argument("--discussion-meeting",
                                    help="optional meeting whose Chair Note contains the reference")
    for name, help_text in (
        ("historical-discussion-coverage", "build bounded offline meeting-range Chair Note coverage"),
        ("plan-historical-corpus", "plan missing historical contribution bodies; never download"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        _add_wg(command)
        command.add_argument("--from-meeting", required=True)
        command.add_argument("--to-meeting", required=True)
        command.add_argument("--query", required=True)
        command.add_argument("--snapshot", action="append", default=[], metavar="MEETING=SNAPSHOT_ID",
                             help="request-scoped explicit Chair Note snapshot selection")
        command.add_argument("--include-metadata-candidates", action=argparse.BooleanOptionalAction,
                             default=True)
        command.add_argument("--limit", type=int, default=100)
        command.add_argument("--max-meetings", type=int, default=24)
        if name == "plan-historical-corpus":
            command.add_argument("--batch", type=int, help="compile one 1-based eligible batch")
            command.add_argument("--fetch-plan", type=Path,
                                 help="write an existing-format TDocFetchPlan YAML; never execute")
    build_links = subparsers.add_parser(
        "build-explicit-links",
        help="build and persist explicit links from already-local evidence; never downloads",
    )
    _add_link_scope_arguments(build_links)
    show_tdoc_links = subparsers.add_parser(
        "show-tdoc-links", help="show local explicit links centered on one TDoc")
    _add_wg(show_tdoc_links)
    show_tdoc_links.add_argument("--tdoc", required=True)
    show_tdoc_study = subparsers.add_parser(
        "show-tdoc-study", help="show a research-facing local TDoc study; never downloads")
    _add_wg(show_tdoc_study)
    show_tdoc_study.add_argument("--tdoc", required=True)
    show_tdoc_study.add_argument(
        "--provenance", action="store_true",
        help="include internal evidence references, links, states, and identities")
    show_meeting_links = subparsers.add_parser(
        "show-meeting-links", help="show local explicit links for one metadata meeting")
    _add_wg_meeting(show_meeting_links)
    show_topic_links = subparsers.add_parser(
        "show-topic-links", help="show explicit links over V0.7 historical topic coverage")
    _add_link_topic_arguments(show_topic_links)
    prepare_links = subparsers.add_parser(
        "plan-link-preparation", help="report missing local inputs without executing preparation")
    _add_link_scope_arguments(prepare_links)
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


def _add_link_topic_arguments(parser: argparse.ArgumentParser) -> None:
    _add_wg(parser)
    parser.add_argument("--from-meeting", required=True)
    parser.add_argument("--to-meeting", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--snapshot", action="append", default=[], metavar="MEETING=SNAPSHOT_ID")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-meetings", type=int, default=24)


def _add_link_scope_arguments(parser: argparse.ArgumentParser) -> None:
    _add_wg(parser)
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--tdoc")
    scope.add_argument("--meeting")
    scope.add_argument("--from-meeting")
    parser.add_argument("--to-meeting")
    parser.add_argument("--query")
    parser.add_argument("--snapshot", action="append", default=[], metavar="MEETING=SNAPSHOT_ID")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--max-meetings", type=int, default=24)


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
    if args.command == "show-tdoc-study":
        from threegpp.study_view import TDocStudyService, render_tdoc_study
        with MetadataRepository(args.db) as repository:
            view = TDocStudyService(repository, args.data_dir).build(args.wg, args.tdoc)
            print(render_tdoc_study(view, provenance=args.provenance), end="")
        return 0
    if args.command in {"build-explicit-links", "show-tdoc-links", "show-meeting-links",
                        "show-topic-links", "plan-link-preparation"}:
        from threegpp.links import ExplicitLinkService
        with MetadataRepository(args.db) as repository:
            service = ExplicitLinkService(repository, args.data_dir)
            graph = _build_link_graph(service, args)
            if args.command == "build-explicit-links":
                path = service.persist(graph)
                _json({"graph": graph.model_dump(mode="json"), "derived_path": str(path),
                       "tdoc_status_path": str(
                           service.data_root / service.tdoc_status_relative_path(graph)),
                       "downloads_performed": 0})
            elif args.command == "plan-link-preparation":
                _json(service.plan_preparation(graph))
            else:
                _json(graph)
        return 0
    if args.command in {"historical-metadata-resolve", "historical-discussion-coverage",
                        "plan-historical-corpus"}:
        from threegpp.historical import (
            HistoricalCoverageRequest, HistoricalCoverageService, HistoricalMetadataResolver,
        )
        with MetadataRepository(args.db) as repository:
            if args.command == "historical-metadata-resolve":
                _json(HistoricalMetadataResolver(repository).resolve(
                    args.wg, args.tdoc, discussion_meeting=args.discussion_meeting,
                    expected_meeting=args.meeting))
                return 0
            snapshots = {}
            for value in args.snapshot:
                if "=" not in value:
                    raise ValueError("--snapshot must use MEETING=SNAPSHOT_ID")
                meeting, snapshot_id = value.split("=", 1)
                if not meeting or not snapshot_id:
                    raise ValueError("--snapshot must use MEETING=SNAPSHOT_ID")
                snapshots[meeting] = snapshot_id
            request = HistoricalCoverageRequest(working_group=args.wg,
                from_meeting=args.from_meeting, to_meeting=args.to_meeting, query=args.query,
                chair_note_snapshots=snapshots,
                include_metadata_candidates=args.include_metadata_candidates,
                limit_per_meeting=args.limit, max_meetings=args.max_meetings)
            service = HistoricalCoverageService(repository, args.data_dir)
            if args.command == "historical-discussion-coverage":
                _json(service.build_coverage(request))
            else:
                if bool(args.batch) != bool(args.fetch_plan):
                    raise ValueError("--batch and --fetch-plan must be supplied together")
                plan = service.plan_corpus(request)
                if args.fetch_plan:
                    service.compile_fetch_plan(plan, args.batch).to_yaml(args.fetch_plan)
                _json(plan)
        return 0
    if args.command in {"discover-chair-notes", "fetch-chair-note", "inspect-chair-note",
                        "discussion-coverage", "plan-topic-corpus"}:
        from threegpp.chair_notes.service import ChairNoteService
        from threegpp.chair_notes.coverage import DiscussionCoverageService
        from threegpp.chair_notes.models import DiscussionCoverageRequest

        chairs = ChairNoteService(args.data_dir)
        if args.command == "discover-chair-notes":
            source = source_for(args.wg)
            try:
                _json(chairs.discover(source, args.meeting))
            finally:
                source.close()
        elif args.command == "fetch-chair-note":
            _json(chairs.fetch(args.wg, args.meeting, args.snapshot, refresh=args.refresh))
        elif args.command == "inspect-chair-note":
            _json(chairs.inspect(args.wg, args.meeting, args.snapshot))
        else:
            with MetadataRepository(args.db) as repository:
                service = DiscussionCoverageService(repository, args.data_dir)
                request = DiscussionCoverageRequest(working_group=args.wg, meeting=args.meeting,
                    query=args.query, chair_note_snapshot=args.snapshot,
                    include_metadata_candidates=args.include_metadata_candidates, limit=args.limit)
                if args.command == "discussion-coverage":
                    _json(service.build_coverage(request))
                else:
                    if bool(args.tdoc) != bool(args.fetch_plan):
                        raise ValueError("--tdoc and --fetch-plan must be supplied together")
                    plan = service.plan_topic_corpus(request)
                    if args.fetch_plan:
                        service.compile_fetch_plan(plan, args.tdoc).to_yaml(args.fetch_plan)
                    _json(plan)
        return 0
    if args.command in {"inspect-meeting-authority", "study-topic"}:
        from threegpp.models import TopicStudyRequest
        from threegpp.topic import TopicStudyService
        with MetadataRepository(args.db) as repository:
            service = TopicStudyService(repository, args.data_dir)
            if args.command == "inspect-meeting-authority":
                _json(service.inspect_meeting_authority(args.tdoc))
            else:
                _json(service.build_topic_study(TopicStudyRequest(
                    query=args.query, working_groups=args.wg or [],
                    authority_meetings=args.authority_meeting or [],
                    discovery_meetings=args.discovery_meeting or [],
                    organizations=args.organization or [], evidence_kinds=args.kind or [],
                    limit_per_group=args.limit)))
        return 0
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


def _build_link_graph(service, args):
    if getattr(args, "tdoc", None):
        return service.build_for_tdoc(args.wg, args.tdoc)
    if getattr(args, "from_meeting", None):
        if not getattr(args, "to_meeting", None) or not getattr(args, "query", None):
            raise ValueError("--from-meeting requires --to-meeting and --query")
        from threegpp.historical import HistoricalCoverageRequest
        snapshots = {}
        for value in getattr(args, "snapshot", []):
            if "=" not in value:
                raise ValueError("--snapshot must use MEETING=SNAPSHOT_ID")
            meeting, snapshot_id = value.split("=", 1)
            if not meeting or not snapshot_id:
                raise ValueError("--snapshot must use MEETING=SNAPSHOT_ID")
            snapshots[meeting] = snapshot_id
        return service.build_for_topic(HistoricalCoverageRequest(
            working_group=args.wg, from_meeting=args.from_meeting,
            to_meeting=args.to_meeting, query=args.query,
            chair_note_snapshots=snapshots,
            limit_per_meeting=getattr(args, "limit", 100),
            max_meetings=getattr(args, "max_meetings", 24)))
    return service.build_for_meeting(args.wg, args.meeting)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (SourceError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"error: {exc}\n")


if __name__ == "__main__":
    sys.exit(main())
