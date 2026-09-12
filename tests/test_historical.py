from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from threegpp.chair_notes.rules import discovered_snapshot
from threegpp.chair_notes.service import ChairNoteService
from threegpp.db import MetadataRepository
from threegpp.documents.models import TDocFetchPlan
from threegpp.historical import (
    HistoricalCoverageRequest, HistoricalCoverageService, HistoricalMetadataResolver,
    HistoricalResolutionState,
)
from threegpp.historical.models import HistoricalCompleteness, MeetingCoverageState
from threegpp.historical.rules import (
    expand_numeric_range, meeting_order_key, normalize_historical_meeting,
)
from threegpp.ingest.downloader import HTTPDownloader
from threegpp.models import SnapshotRole, TDocListSnapshot, TDocMetadata

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def chair(group, meeting, filename="chair_notes_final.txt"):
    directory = f"https://www.3gpp.org/ftp/fixture/{group}/{meeting}/Inbox/Chair_notes/"
    return discovered_snapshot(group, meeting, directory + filename, directory, NOW)


def install_chair(root: Path, group: str, meeting: str, text: str, filename="chair_notes_final.txt"):
    item = chair(group, meeting, filename)
    with httpx.Client(transport=httpx.MockTransport(
            lambda request: httpx.Response(200, content=text.encode()))) as client:
        service = ChairNoteService(root, HTTPDownloader(client=client))
        source = SimpleNamespace(working_group=group, discover_chair_notes=lambda value: [item])
        service.discover(source, meeting)
        service.fetch(group, meeting, item.snapshot_id)
    return item


def metadata(tdoc_id, meeting, *, group="RAN1", title="HARQ contribution", downloadable=True):
    return TDocMetadata(tdoc_id=tdoc_id, working_group=group, meeting=meeting, title=title,
        source_organization_raw="Example Org", organizations=["Example Org"],
        official_list_present=True, metadata_source_kind="tdoc_list",
        metadata_source_url=f"https://www.3gpp.org/{group}/{meeting}/list.xlsx",
        metadata_source_checksum="a" * 64,
        source_url=(f"https://www.3gpp.org/{group}/{meeting}/{tdoc_id}.zip" if downloadable else None))


def add_snapshot(repo, meeting, rows, *, group="RAN1", suffix="a", role=SnapshotRole.HISTORICAL):
    snapshot = TDocListSnapshot(source_url=f"https://www.3gpp.org/{group}/{meeting}/list-{suffix}.xlsx",
        working_group=group, meeting=meeting, filename=f"list-{suffix}.xlsx",
        checksum=(suffix[0].encode().hex()[0] * 64), roles=[role], snapshot_timestamp=NOW,
        row_count=len(rows), tdocs=rows)
    repo.upsert_tdoc_list_snapshot(snapshot)
    return snapshot


@pytest.mark.parametrize("raw", ["124b", "124bis", "RAN1#124b", "RAN1#124bis", "TSGR1_124b"])
def test_meeting_aliases_preserve_raw_and_normalize(raw):
    normalized, source_alias = normalize_historical_meeting(raw, "RAN1")
    assert normalized == "124bis"
    assert (source_alias is not None) == raw.casefold().endswith("b")


@pytest.mark.parametrize("raw", ["124", "125", "119-e"])
def test_non_alias_meetings_remain_distinct(raw):
    normalized, alias = normalize_historical_meeting(raw, "RAN1")
    assert normalized == raw and alias is None


def test_scoped_alias_rejects_mixed_working_group():
    with pytest.raises(ValueError, match="belongs to RAN2"):
        normalize_historical_meeting("RAN2#124b", "RAN1")


def test_range_chronology_and_validation():
    assert expand_numeric_range("124", "126", ["124bis"]) == ["124", "124bis", "125", "126"]
    assert meeting_order_key("124") < meeting_order_key("124bis") < meeting_order_key("125")
    with pytest.raises(ValueError, match="must not follow"):
        expand_numeric_range("126", "124")


def test_electronic_meeting_orders_before_next_numeric_meeting():
    assert meeting_order_key("119-e") < meeting_order_key("120")


def test_historical_resolution_preserves_snapshot_provenance(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        snap = add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis")])
        result = HistoricalMetadataResolver(repo).resolve(
            "RAN1", "R1-2603427", discussion_meeting="125", expected_meeting="124b")
        assert result.state is HistoricalResolutionState.HISTORICAL_METADATA
        assert result.selected.metadata.meeting == "124bis"
        assert result.discussion_meeting == "125"
        assert result.selected.snapshot_url == str(snap.source_url)
        assert result.selected.snapshot_id.startswith("tdoc-list-")
        assert result.selected.snapshot_filename == snap.filename
        assert result.selected.snapshot_checksum == snap.checksum


def test_current_exact_precedes_historical_duplicate(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        current = metadata("R1-2603427", "124bis", title="Current exact")
        repo.upsert_tdoc(current)
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", title="Current exact")])
        result = HistoricalMetadataResolver(repo).resolve(
            "RAN1", "R1-2603427", expected_meeting="124bis")
        assert result.state is HistoricalResolutionState.CURRENT_MEETING_METADATA
        assert result.selected.metadata.title == "Current exact"
        assert result.selected.source_layer == "canonical_current"
        assert len(result.candidates) == 2


def test_other_current_meeting_and_unresolved_are_distinct(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        repo.upsert_tdoc(metadata("R1-2603427", "125"))
        resolver = HistoricalMetadataResolver(repo)
        assert resolver.resolve("RAN1", "R1-2603427", expected_meeting="124bis").state is HistoricalResolutionState.OTHER_KNOWN_METADATA
        assert resolver.resolve("RAN1", "R1-2699999", expected_meeting="124bis").state is HistoricalResolutionState.UNRESOLVED


def test_listed_only_historical_record_has_no_fabricated_url(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", downloadable=False)])
        result = HistoricalMetadataResolver(repo).resolve("RAN1", "R1-2603427", expected_meeting="124bis")
        assert result.state is HistoricalResolutionState.LISTED_ONLY
        assert result.selected.metadata.source_url is None


def test_unknown_historical_availability_remains_unknown(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        row = TDocMetadata(tdoc_id="R1-2603427", working_group="RAN1", meeting="124bis")
        add_snapshot(repo, "124bis", [row])
        result = HistoricalMetadataResolver(repo).resolve("RAN1", "R1-2603427",
                                                          expected_meeting="124bis")
        assert result.state is HistoricalResolutionState.UNKNOWN
        assert result.selected.metadata.source_url is None


def test_incompatible_historical_candidates_are_ambiguous_and_retained(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", title="A")], suffix="a")
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", title="B")], suffix="b")
        result = HistoricalMetadataResolver(repo).resolve("RAN1", "R1-2603427", expected_meeting="124bis")
        assert result.state is HistoricalResolutionState.AMBIGUOUS
        assert result.selected is None and len(result.candidates) == 2


def test_meeting_close_snapshot_precedes_provisional_historical_snapshot(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        close = add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", title="Close")],
                             suffix="c", role=SnapshotRole.MEETING_CLOSE)
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis", title="Provisional")],
                     suffix="p", role=SnapshotRole.HISTORICAL)
        result = HistoricalMetadataResolver(repo).resolve("RAN1", "R1-2603427",
                                                          expected_meeting="124bis")
        assert result.selected.snapshot_url == str(close.source_url)
        assert result.selected.metadata.title == "Close"
        assert len(result.candidates) == 2


def test_ran2_historical_resolution_is_generic(tmp_path):
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        add_snapshot(repo, "134bis", [metadata("R2-2603427", "134bis", group="RAN2")], group="RAN2")
        result = HistoricalMetadataResolver(repo).resolve("RAN2", "R2-2603427", expected_meeting="RAN2#134b")
        assert result.selected.metadata.working_group.value == "RAN2"


def test_range_reuses_single_meeting_coverage_and_resolves_archived_metadata(tmp_path, monkeypatch):
    install_chair(tmp_path, "RAN1", "125", "HARQ Fast-ARQ R1-2603427")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        add_snapshot(repo, "124bis", [metadata("R1-2603427", "124bis")])
        service = HistoricalCoverageService(repo, tmp_path)
        request = HistoricalCoverageRequest(working_group="RAN1", from_meeting="124b",
            to_meeting="126", query="HARQ Fast-ARQ")
        first = service.build_coverage(request)
        second = service.build_coverage(request)
        assert first == second
        assert [m.meeting.meeting for m in first.meetings] == ["124bis", "125", "126"]
        assert first.meetings[0].meeting.raw_text == "124b"
        assert first.meetings[0].meeting.source_alias == "124b"
        assert first.meetings[0].state is MeetingCoverageState.CHAIR_NOTE_UNAVAILABLE
        assert first.meetings[1].historical_resolutions[0].state is HistoricalResolutionState.HISTORICAL_METADATA
        assert first.meetings[1].coverage.chair_note_confirmed[0].metadata.meeting == "124bis"
        assert first.meetings[2].state is MeetingCoverageState.CHAIR_NOTE_UNAVAILABLE
        assert first.completeness is HistoricalCompleteness.PARTIAL_SOURCE_COVERAGE
        assert "not evidence" in first.limitations[0]
        assert repo.connection.execute("select count(*) from semantic_evidence").fetchone()[0] == 0


def test_ambiguous_snapshot_does_not_abort_range_or_select(tmp_path):
    chairs = ChairNoteService(tmp_path)
    items = [chair("RAN1", "125", "chair_notes_eom1.txt"),
             chair("RAN1", "125", "chair_notes_eom2.txt")]
    chairs.discover(SimpleNamespace(working_group="RAN1", discover_chair_notes=lambda meeting: items), "125")
    install_chair(tmp_path, "RAN1", "126", "HARQ")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="125", to_meeting="126", query="HARQ"))
        assert result.meetings[0].state is MeetingCoverageState.SNAPSHOT_SELECTION_REQUIRED
        assert result.meetings[0].coverage.selection.selected_snapshot is None
        assert result.meetings[1].state is MeetingCoverageState.AVAILABLE


def test_explicit_snapshot_resolves_ambiguous_chair_selection(tmp_path):
    items = [chair("RAN1", "125", "chair_notes_eom1.txt"),
             chair("RAN1", "125", "chair_notes_eom2.txt")]
    for item in items:
        with httpx.Client(transport=httpx.MockTransport(
                lambda request: httpx.Response(200, content=b"HARQ R1-2699999"))) as client:
            chairs = ChairNoteService(tmp_path, HTTPDownloader(client=client))
            chairs.discover(SimpleNamespace(working_group="RAN1",
                discover_chair_notes=lambda meeting: items), "125")
            chairs.fetch("RAN1", "125", item.snapshot_id)
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        request = HistoricalCoverageRequest(working_group="RAN1", from_meeting="125",
            to_meeting="125", query="HARQ", chair_note_snapshots={"125": items[0].snapshot_id})
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(request)
        assert result.meetings[0].state is MeetingCoverageState.AVAILABLE
        assert result.meetings[0].coverage.selection.selected_snapshot.snapshot_id == items[0].snapshot_id


def test_explicit_final_selection_and_metadata_only_separation(tmp_path):
    final = install_chair(tmp_path, "RAN1", "126", "HARQ R1-2601001")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        repo.upsert_tdoc(metadata("R1-2601001", "126"))
        repo.upsert_tdoc(metadata("R1-2601002", "126", title="HARQ metadata only"))
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="126", to_meeting="126", query="HARQ"))
        meeting = result.meetings[0]
        assert meeting.coverage.selection.selected_snapshot.snapshot_id == final.snapshot_id
        assert [x.tdoc_id for x in meeting.coverage.chair_note_confirmed] == ["R1-2601001"]
        assert [x.tdoc_id for x in meeting.coverage.metadata_relevant_only] == ["R1-2601002"]


def test_metadata_snapshot_tie_is_reported_for_source_preparation(tmp_path):
    install_chair(tmp_path, "RAN1", "126", "HARQ")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        add_snapshot(repo, "126", [], suffix="a", role=SnapshotRole.HISTORICAL)
        add_snapshot(repo, "126", [], suffix="b", role=SnapshotRole.HISTORICAL)
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="126", to_meeting="126", query="HARQ"))
        assert result.meetings[0].metadata_source_state.value == "snapshot_selection_required"
        assert result.meetings[0].preferred_metadata_snapshot_url is None


def test_metadata_source_failure_is_not_reported_as_tdoc_absence(tmp_path):
    install_chair(tmp_path, "RAN1", "126", "HARQ")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        failed = TDocListSnapshot(source_url="https://www.3gpp.org/RAN1/126/list.xlsx",
            working_group="RAN1", meeting="126", filename="list.xlsx", roles=[SnapshotRole.HISTORICAL],
            parse_error="source unavailable: HTTP 403", tdocs=[])
        repo.upsert_tdoc_list_snapshot(failed)
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="126", to_meeting="126", query="HARQ"))
        assert result.meetings[0].metadata_source_state.value == "source_unavailable"
        assert result.meetings[0].metadata_snapshots[0].parse_error == "source unavailable: HTTP 403"


def test_chair_note_agreement_text_never_creates_meeting_evidence(tmp_path):
    install_chair(tmp_path, "RAN1", "126", "HARQ Agreement: Study Fast-ARQ. R1-2603427")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        repo.upsert_tdoc(metadata("R1-2603427", "126"))
        result = HistoricalCoverageService(repo, tmp_path).build_coverage(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="126", to_meeting="126", query="HARQ"))
        assert result.meetings[0].coverage.chair_note_confirmed
        assert repo.connection.execute("select count(*) from semantic_evidence").fetchone()[0] == 0


def test_plan_deduplicates_body_and_preserves_multiple_refs(tmp_path, monkeypatch):
    install_chair(tmp_path, "RAN1", "125", "HARQ R1-2603427 R1-2603427")
    install_chair(tmp_path, "RAN1", "126", "HARQ R1-2603427")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        repo.upsert_tdoc(metadata("R1-2603427", "124bis"))
        service = HistoricalCoverageService(repo, tmp_path)
        request = HistoricalCoverageRequest(working_group="RAN1", from_meeting="125",
            to_meeting="126", query="HARQ")
        plan = service.plan_corpus(request)
        assert plan == service.plan_corpus(request)
        assert len(plan.items) == 1 and len(plan.items[0].associations) == 3
        assert {edge.discussion_meeting for edge in plan.items[0].associations} == {"125", "126"}
        assert plan.batches == [["R1-2603427"]]
        fetch = service.compile_fetch_plan(plan, 1)
        assert isinstance(fetch, TDocFetchPlan) and len(fetch.items) == 1
        assert fetch.items[0].meeting == "124bis"


def test_plan_batches_at_existing_limit_and_never_executes(tmp_path, monkeypatch):
    ids = [f"R1-{2600000 + index}" for index in range(55)]
    install_chair(tmp_path, "RAN1", "126", "HARQ " + " ".join(ids))
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        for tdoc_id in ids:
            repo.upsert_tdoc(metadata(tdoc_id, "126"))
        from threegpp.documents import DocumentService
        monkeypatch.setattr(DocumentService, "execute", lambda *args: pytest.fail("planning downloaded"))
        plan = HistoricalCoverageService(repo, tmp_path).plan_corpus(HistoricalCoverageRequest(
            working_group="RAN1", from_meeting="126", to_meeting="126", query="HARQ"))
        assert [len(batch) for batch in plan.batches] == [50, 5]


def test_range_safety_and_rule_identity_invalidation(tmp_path, monkeypatch):
    from threegpp.historical import rules
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        service = HistoricalCoverageService(repo, tmp_path)
        with pytest.raises(ValueError, match="maximum"):
            service.build_coverage(HistoricalCoverageRequest(working_group="RAN1",
                from_meeting="100", to_meeting="126", query="HARQ", max_meetings=5))
        request = HistoricalCoverageRequest(working_group="RAN1", from_meeting="126",
            to_meeting="126", query="HARQ")
        first = service.build_coverage(request)
        monkeypatch.setattr(rules, "HISTORICAL_METADATA_RESOLVER_VERSION", "changed")
        assert service.build_coverage(request).coverage_id != first.coverage_id


def test_snapshot_checksum_change_invalidates_resolution_and_plan_identity(tmp_path):
    install_chair(tmp_path, "RAN1", "126", "HARQ R1-2603427")
    with MetadataRepository(tmp_path / "m.duckdb") as repo:
        row = metadata("R1-2603427", "124bis")
        first_snapshot = add_snapshot(repo, "124bis", [row], suffix="a")
        service = HistoricalCoverageService(repo, tmp_path)
        request = HistoricalCoverageRequest(working_group="RAN1", from_meeting="126",
            to_meeting="126", query="HARQ")
        first = service.plan_corpus(request)
        changed = first_snapshot.model_copy(update={"checksum": "f" * 64})
        repo.upsert_tdoc_list_snapshot(changed)
        second = service.plan_corpus(request)
        assert second.plan_id != first.plan_id
        with pytest.raises(ValueError, match="stale"):
            service.compile_fetch_plan(first, 1)


def test_historical_cli_commands_use_local_state_only(tmp_path, capsys, monkeypatch):
    from threegpp.cli import main
    from threegpp.documents import DocumentService

    install_chair(tmp_path, "RAN1", "126", "HARQ R1-2603427")
    database = tmp_path / "m.duckdb"
    with MetadataRepository(database) as repo:
        repo.upsert_tdoc(metadata("R1-2603427", "124bis"))
    monkeypatch.setattr(DocumentService, "execute", lambda *args: pytest.fail("CLI downloaded"))
    common = ["--db", str(database), "--data-dir", str(tmp_path)]
    scope = ["--wg", "RAN1", "--from-meeting", "126", "--to-meeting", "126",
             "--query", "HARQ Fast-ARQ"]
    assert main(common + ["historical-metadata-resolve", "--wg", "RAN1", "--meeting",
                          "124b", "--discussion-meeting", "126", "--tdoc", "R1-2603427"]) == 0
    assert '"selected"' in capsys.readouterr().out
    assert main(common + ["historical-discussion-coverage"] + scope) == 0
    assert '"coverage_id"' in capsys.readouterr().out
    assert main(common + ["plan-historical-corpus"] + scope) == 0
    assert '"plan_id"' in capsys.readouterr().out
