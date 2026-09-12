from __future__ import annotations

import io
import zipfile

import pytest

from threegpp.completion import (
    CompletionFailure, CompletionStageState, TDocEvidenceCompletionRequest,
    TDocEvidenceCompletionService, render_completion_result,
)
from threegpp.cli import main
from threegpp.db import MetadataRepository
from threegpp.documents.models import RetentionState
from threegpp.evidence import EvidenceExtractionService
from threegpp.ingest.downloader import DownloadResult
from threegpp.links import ExplicitLinkService
from threegpp.models import (
    DocumentRole, EvidenceExtractionOutcome, EvidenceExtractionRequest, EvidenceScope,
    IndexOutcome, TDocMetadata,
)
from threegpp.study_view import TDocStudyService, render_tdoc_study

from test_documents import FakeDownloader
from test_historical import add_snapshot, metadata
from test_links import discussion


def package(text="Proposal: Use explicit DCI for Fast ARQ."):
    target = io.BytesIO()
    with zipfile.ZipFile(target, "w") as archive:
        archive.writestr("contribution.txt", text)
    return target.getvalue()


def request(tdoc_id="R1-2604142", **values):
    return TDocEvidenceCompletionRequest(
        working_group="RAN1", tdoc_id=tdoc_id, **values)


def setup_service(tmp_path, *, record=None, text=None):
    repository = MetadataRepository(tmp_path / "metadata.duckdb")
    record = record or metadata("R1-2604142", "126")
    repository.upsert_tdoc(record)
    downloader = FakeDownloader(package(text or "Proposal: Use explicit DCI for Fast ARQ."))
    return repository, downloader, TDocEvidenceCompletionService(
        repository, tmp_path, downloader)


def test_explicit_completion_fetches_one_tdoc_and_replay_reuses_every_stage(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    neighbor = metadata("R1-2604143", "126")
    repository.upsert_tdoc(neighbor)
    before = TDocStudyService(repository, tmp_path).build("RAN1", "R1-2604142")
    first = service.complete(request())
    second = service.complete(request())
    after = TDocStudyService(repository, tmp_path).build("RAN1", "R1-2604142")
    neighbor_receipt = repository.get_document_receipt("R1-2604143", "RAN1", "126")
    repository.close()

    assert before.contribution.content_inspected is False
    assert first.failure is None and first.content_inspected is True
    assert after.contribution.content_inspected is True
    assert downloader.calls == 1 and neighbor_receipt is None
    assert first.retention is RetentionState.CACHE
    assert second.body.state is CompletionStageState.REUSED
    assert second.normalization.state is CompletionStageState.REUSED
    assert second.index.state is CompletionStageState.REUSED
    assert second.semantic_extraction.state is CompletionStageState.REUSED
    assert first.result_id == second.result_id
    assert first.study_view_id == second.study_view_id == after.view_id
    assert before.discussion == after.discussion
    assert before.meeting_outcome == after.meeting_outcome


def test_default_and_explicit_retention_transitions_do_not_redownload(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    cached = service.complete(request())
    pinned = service.complete(request(retention=RetentionState.PINNED))
    preserved = service.complete(request())
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    repository.close()
    assert cached.retention is RetentionState.CACHE
    assert pinned.retention is RetentionState.PINNED
    assert preserved.retention is RetentionState.PINNED
    assert receipt.raw.retention is RetentionState.PINNED
    assert downloader.calls == 1


def test_initial_pinned_request_fetches_once_and_never_deletes_raw(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    result = service.complete(request(retention=RetentionState.PINNED))
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    raw_path = receipt.raw.local_path
    repository.close()
    assert result.retention is RetentionState.PINNED
    assert downloader.calls == 1 and raw_path.is_file()


def test_offline_missing_body_returns_gap_without_download(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    result = service.complete(request(offline=True))
    repository.close()
    assert result.failure is CompletionFailure.OFFLINE_BODY_MISSING
    assert result.body.state is CompletionStageState.BLOCKED
    assert result.content_inspected is False and downloader.calls == 0


@pytest.mark.parametrize("availability", ["listed", "unknown"])
def test_non_downloadable_metadata_never_guesses_a_url(tmp_path, availability):
    if availability == "listed":
        record = metadata("R1-2604142", "126", downloadable=False)
    else:
        record = TDocMetadata(tdoc_id="R1-2604142", working_group="RAN1", meeting="126",
                              title="Fast ARQ contribution", organizations=["Example Org"])
    repository, downloader, service = setup_service(tmp_path, record=record)
    result = service.complete(request())
    repository.close()
    assert result.failure is CompletionFailure.BODY_NOT_DOWNLOADABLE
    assert result.content_inspected is False and downloader.calls == 0
    assert result.metadata.values["availability"] in {"listed_only", "unknown"}


def test_unresolved_and_ambiguous_metadata_block_acquisition(tmp_path):
    repository = MetadataRepository(tmp_path / "metadata.duckdb")
    downloader = FakeDownloader(package())
    service = TDocEvidenceCompletionService(repository, tmp_path, downloader)
    unresolved = service.complete(request())
    repository.upsert_tdoc(metadata("R1-2604142", "125", title="First"))
    repository.upsert_tdoc(metadata("R1-2604142", "126", title="Second"))
    ambiguous = service.complete(request())
    repository.close()
    assert unresolved.failure is CompletionFailure.METADATA_UNRESOLVED
    assert ambiguous.failure is CompletionFailure.METADATA_AMBIGUOUS
    assert downloader.calls == 0


def test_offline_reuses_raw_and_rebuilds_missing_downstream_state(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    service.complete(request())
    repository.connection.execute(
        "UPDATE search_index_state SET status='STALE' WHERE tdoc_id='R1-2604142'")
    repository.connection.execute(
        "UPDATE semantic_evidence_state SET status='STALE' WHERE tdoc_id='R1-2604142'")
    repository.connection.execute(
        "DELETE FROM semantic_evidence WHERE tdoc_id='R1-2604142'")
    replay = service.complete(request(offline=True))
    repository.close()
    assert replay.failure is None and replay.content_inspected is True
    assert replay.body.state is CompletionStageState.REUSED
    assert replay.normalization.state is CompletionStageState.REUSED
    assert replay.index.state is CompletionStageState.COMPLETED
    assert replay.semantic_extraction.state is CompletionStageState.COMPLETED
    assert downloader.calls == 1


def test_offline_normalizes_a_cached_raw_body_without_a_receipt(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    raw = tmp_path / "raw/tdocs/ran1/126/R1-2604142/R1-2604142.zip"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(package())
    result = service.complete(request(offline=True))
    repository.close()
    assert result.failure is None and result.content_inspected is True
    assert result.body.state is CompletionStageState.REUSED
    assert result.normalization.state is CompletionStageState.COMPLETED
    assert downloader.calls == 0


def test_stale_normalization_rebuilds_from_raw_without_download(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    service.complete(request())
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    (tmp_path / receipt.normalized_path).write_bytes(b"stale")
    repaired = service.complete(request(offline=True))
    repository.close()
    assert repaired.failure is None
    assert repaired.body.state is CompletionStageState.REUSED
    assert repaired.normalization.state is CompletionStageState.COMPLETED
    assert downloader.calls == 1


def test_pinned_retention_survives_local_renormalization(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    service.complete(request(retention=RetentionState.PINNED))
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    (tmp_path / receipt.normalized_path).write_bytes(b"stale")
    repaired = service.complete(request())
    final_receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    repository.close()
    assert repaired.failure is None and repaired.retention is RetentionState.PINNED
    assert final_receipt.raw.retention is RetentionState.PINNED
    assert downloader.calls == 1


def test_raw_checksum_conflict_blocks_processing_without_redownload(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    service.complete(request())
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    receipt.raw.local_path.write_bytes(b"changed")
    result = service.complete(request())
    repository.close()
    assert result.failure is CompletionFailure.RAW_CHECKSUM_INVALID
    assert result.body.state is CompletionStageState.FAILED
    assert downloader.calls == 1


def test_download_and_normalization_failures_remain_distinct(tmp_path):
    class FailedDownloader:
        def download(self, *args):
            raise RuntimeError("synthetic download failure")

    repository = MetadataRepository(tmp_path / "download/metadata.duckdb")
    repository.upsert_tdoc(metadata("R1-2604142", "126"))
    download = TDocEvidenceCompletionService(
        repository, tmp_path / "download", FailedDownloader()).complete(request())
    repository.close()

    repository, downloader, service = setup_service(tmp_path / "normalize")
    downloader.data = b"not a valid ZIP package"
    normalization = service.complete(request())
    repository.close()
    assert download.failure is CompletionFailure.DOWNLOAD_FAILED
    assert normalization.failure is CompletionFailure.NORMALIZATION_FAILED
    assert normalization.body.state is CompletionStageState.COMPLETED


def test_index_failure_stops_before_semantic_extraction(tmp_path, monkeypatch):
    repository, downloader, service = setup_service(tmp_path)
    monkeypatch.setattr(service.search, "index_document", lambda receipt:
        IndexOutcome(tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
                     meeting=receipt.meeting, status="FAILED"))
    monkeypatch.setattr(
        service.evidence, "extract_document",
        lambda receipt: pytest.fail("semantic extraction ran after index failure"))
    result = service.complete(request())
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    repository.close()
    assert result.failure is CompletionFailure.INDEX_FAILED
    assert result.index.state is CompletionStageState.FAILED
    assert result.semantic_extraction.state is CompletionStageState.NOT_RUN
    assert result.content_inspected is False
    assert receipt.raw.local_path.is_file() and downloader.calls == 1


def test_successful_zero_evidence_extraction_is_inspected(tmp_path):
    repository, downloader, service = setup_service(
        tmp_path, text="Background text without an explicit evidence label.")
    result = service.complete(request())
    view = TDocStudyService(repository, tmp_path).build("RAN1", "R1-2604142")
    output = render_completion_result(result)
    repository.close()
    assert result.failure is None and result.evidence_count == 0
    assert result.content_inspected is True and view.contribution.evidence == []
    assert "No qualifying contribution statements were extracted" in output


def test_extraction_failure_retains_raw_and_retry_does_not_redownload(tmp_path, monkeypatch):
    repository, downloader, service = setup_service(tmp_path)
    real_extract = service.evidence.extract_document
    monkeypatch.setattr(service.evidence, "extract_document", lambda receipt:
        EvidenceExtractionOutcome(tdoc_id=receipt.tdoc_id, working_group=receipt.working_group,
            meeting=receipt.meeting, status="FAILED", document_role=DocumentRole.CONTRIBUTION,
            document_role_basis=["synthetic failure"]))
    failed = service.complete(request())
    receipt = repository.get_document_receipt("R1-2604142", "RAN1", "126")
    monkeypatch.setattr(service.evidence, "extract_document", real_extract)
    retried = service.complete(request())
    repository.close()
    assert failed.failure is CompletionFailure.SEMANTIC_EXTRACTION_FAILED
    assert failed.content_inspected is False and receipt.raw.local_path.is_file()
    assert retried.failure is None and retried.content_inspected is True
    assert retried.body.state is CompletionStageState.REUSED
    assert retried.normalization.state is CompletionStageState.REUSED
    assert downloader.calls == 1


def test_historical_snapshot_metadata_preserves_source_meeting_and_url(tmp_path):
    repository = MetadataRepository(tmp_path / "metadata.duckdb")
    historical = metadata("R1-2603427", "124bis")
    add_snapshot(repository, "124bis", [historical])
    downloader = FakeDownloader(package())
    service = TDocEvidenceCompletionService(repository, tmp_path, downloader)
    result = service.complete(request("R1-2603427", expected_metadata_meeting="124b",
                                      discussion_meeting="125"))
    evidence = EvidenceExtractionService(repository, tmp_path).list_evidence(
        EvidenceExtractionRequest(tdoc_ids=["R1-2603427"]))
    receipt = repository.get_document_receipt("R1-2603427", "RAN1", "124bis")
    repository.close()
    assert result.failure is None and result.metadata_resolution.selected.metadata.meeting == "124bis"
    assert result.metadata_resolution.discussion_meeting == "125"
    assert str(receipt.raw.source_url) == str(historical.source_url)
    assert all(item.scope is EvidenceScope.CONTRIBUTION for item in evidence)


def test_study_vocabulary_remains_after_completion(tmp_path):
    repository, downloader, service = setup_service(tmp_path)
    graph = ExplicitLinkService(repository, tmp_path).resolve_links(
        working_group="RAN1", discussion_records=[discussion("R1-2604142")],
        metadata_records=[metadata("R1-2604142", "126")])
    ExplicitLinkService(repository, tmp_path).persist(graph)
    before = TDocStudyService(repository, tmp_path).build("RAN1", "R1-2604142")
    completed = service.complete(request())
    after = TDocStudyService(repository, tmp_path).build("RAN1", "R1-2604142")
    normal = render_tdoc_study(after)
    repository.close()
    assert completed.failure is None and downloader.calls == 1
    assert before.discussion == after.discussion
    assert before.meeting_outcome == after.meeting_outcome
    assert [line for line in normal.splitlines() if line in {
        "DISCUSSION", "CONTRIBUTION", "MEETING OUTCOME", "EVIDENCE STATUS"}] == [
            "DISCUSSION", "CONTRIBUTION", "MEETING OUTCOME"]
    for hidden in ("BODY_NOT_LOCAL", "NO_EXPLICIT_LINK", "graph node", "coverage axis"):
        assert hidden not in normal


def test_read_only_cli_commands_never_acquire_a_body(tmp_path, monkeypatch, capsys):
    from threegpp.ingest.downloader import HTTPDownloader

    database = tmp_path / "metadata.duckdb"
    with MetadataRepository(database) as repository:
        repository.upsert_tdoc(metadata("R1-2604142", "126"))
    monkeypatch.setattr(
        HTTPDownloader, "download",
        lambda *args, **kwargs: pytest.fail("read-only command attempted acquisition"))
    common = ["--db", str(database), "--data-dir", str(tmp_path)]
    commands = [
        ["show-tdoc-study", "--wg", "RAN1", "--tdoc", "R1-2604142"],
        ["show-tdoc-links", "--wg", "RAN1", "--tdoc", "R1-2604142"],
        ["plan-link-preparation", "--wg", "RAN1", "--tdoc", "R1-2604142"],
        ["show-topic-links", "--wg", "RAN1", "--from-meeting", "126",
         "--to-meeting", "126", "--query", "Fast ARQ"],
    ]
    for command in commands:
        assert main(common + command) == 0
    capsys.readouterr()


def test_completion_cli_reports_independent_operational_stages(
        tmp_path, monkeypatch, capsys):
    from threegpp.ingest.downloader import HTTPDownloader

    database = tmp_path / "metadata.duckdb"
    with MetadataRepository(database) as repository:
        repository.upsert_tdoc(metadata("R1-2604142", "126"))

    def download(_self, _url, destination):
        payload = package()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        import hashlib
        return DownloadResult(destination, hashlib.sha256(payload).hexdigest(), True)

    monkeypatch.setattr(HTTPDownloader, "download", download)
    result = main(["--db", str(database), "--data-dir", str(tmp_path),
                   "complete-tdoc-evidence", "--wg", "RAN1",
                   "--tdoc", "R1-2604142"])
    output = capsys.readouterr().out
    assert result == 0
    assert "Metadata                  COMPLETED" in output
    assert "Contribution body         COMPLETED" in output
    assert "Retention                 CACHE" in output
    assert "TDoc content inspected    Yes" in output
