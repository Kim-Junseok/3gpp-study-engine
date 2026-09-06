from pathlib import Path
from io import BytesIO
import hashlib

import httpx
import pytest
from openpyxl import Workbook

from threegpp.db import MetadataRepository
from threegpp.ingest import (
    DownloadConflictError,
    HTTPDownloader,
    ManifestStore,
    MeetingIngestor,
)
from threegpp.ingest.downloader import safe_filename
from threegpp.models import SnapshotRole, StudyRequest, TDocMetadata
from threegpp.study import StudyService


def test_metadata_only_ingestion_writes_manifest_and_database(tmp_path, ran2_source) -> None:
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        ingestor = MeetingIngestor(
            ran2_source,
            repository,
            ManifestStore(tmp_path / "manifests"),
            tmp_path / "raw",
        )
        manifest, path = ingestor.ingest("131")
        stored_tdocs = repository.list_tdocs("RAN2", "131")

    assert path.exists()
    assert manifest.download_artifacts is False
    assert all(artifact.retrieved_at is None for artifact in manifest.artifacts)
    assert len(manifest.artifacts) == 5
    assert len(stored_tdocs) == 2
    assert not (tmp_path / "raw").exists()


def test_safe_filename_preserves_hash_in_plain_official_filename() -> None:
    assert safe_filename("TDoc_List_Meeting_RAN1#125.xlsx", "artifact") == (
        "TDoc_List_Meeting_RAN1#125.xlsx"
    )
    assert safe_filename(
        "https://www.3gpp.org/TDoc_List_Meeting_RAN1%23125.xlsx", "artifact"
    ) == "TDoc_List_Meeting_RAN1%23125.xlsx"


def test_downloader_checksums_caches_and_refuses_changed_bytes(tmp_path) -> None:
    content = [b"original evidence", b"original evidence", b"changed evidence"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content.pop(0), request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = HTTPDownloader(client=client, backoff=0)
    destination = tmp_path / "artifact.zip"

    first = downloader.download("https://www.3gpp.org/artifact.zip", destination)
    second = downloader.download("https://www.3gpp.org/artifact.zip", destination)

    assert first.downloaded is True
    assert second.downloaded is False
    assert first.sha256 == second.sha256
    assert destination.read_bytes() == b"original evidence"

    with pytest.raises(DownloadConflictError):
        downloader.download("https://www.3gpp.org/artifact.zip", destination)
    assert destination.read_bytes() == b"original evidence"
    client.close()


def test_enrichment_parses_all_snapshots_and_builds_current_view(tmp_path, ran2_source) -> None:
    def workbook_bytes(rows: list[list[str]]) -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["TDoc", "Title", "Source", "Abstract", "TDoc Status"])
        for row in rows:
            sheet.append(row)
        buffer = BytesIO()
        workbook.save(buffer)
        return buffer.getvalue()

    consolidated = workbook_bytes(
        [["R2-2505001", "Current uplink title", "Nokia", "", "treated"]]
    )
    meeting_close = workbook_bytes(
        [["R2-2505001", "Close uplink title", "Nokia", "Close abstract", "withdrawn"]]
    )
    historical = workbook_bytes(
        [
            ["R2-2505001", "Historical uplink title", "Nokia", "", "draft"],
            ["R2-2505999", "Historical-only title", "Ericsson", "", "draft"],
        ]
    )
    requests: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if "/Docs/" in str(request.url):
            content = consolidated
        elif "final" in str(request.url):
            content = meeting_close
        else:
            content = historical
        return httpx.Response(200, content=content, request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    downloader = HTTPDownloader(client=client, backoff=0)
    with MetadataRepository(tmp_path / "metadata.duckdb") as repository:
        repository.upsert_tdoc(
            TDocMetadata(
                tdoc_id="R2-2505001",
                working_group="RAN2",
                meeting="131",
                title="Pre-V0.2a.2 title",
                source_url="https://www.3gpp.org/R2-2505001.zip",
            )
        )
        ingestor = MeetingIngestor(
            ran2_source,
            repository,
            ManifestStore(tmp_path / "manifests"),
            tmp_path / "raw",
            downloader,
        )
        manifest, manifest_path = ingestor.ingest("131", enrich_tdocs=True)
        enriched = repository.get_tdoc("RAN2", "131", "R2-2505001")
        historical_only = repository.get_tdoc("RAN2", "131", "R2-2505999")
        stored_snapshots = repository.list_tdoc_list_snapshots("RAN2", "131")

        canonical_ids_before = [item.tdoc_id for item in repository.list_tdocs("RAN2", "131")]
        assert manifest.current_output is not None
        current_path = tmp_path / manifest.current_output.path
        current_checksum_before = hashlib.sha256(current_path.read_bytes()).hexdigest()
        manifest_checksum_before = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        historical_snapshot = next(
            item for item in stored_snapshots if SnapshotRole.HISTORICAL in item.roles
        )
        meeting_close_snapshot = next(
            item for item in stored_snapshots if SnapshotRole.MEETING_CLOSE in item.roles
        )
        request = StudyRequest(
            name="view-isolation",
            working_groups=["RAN2"],
            meetings={"RAN2": ["131"]},
        )
        service = StudyService(repository)
        historical_inventory = service.candidate_inventory(
            request, snapshot_url=str(historical_snapshot.source_url)
        )
        meeting_close_inventory = service.candidate_inventory(
            request, snapshot_url=str(meeting_close_snapshot.source_url)
        )
        canonical_inventory = service.candidate_inventory(request)

        explicit_manifest, explicit_manifest_path = ingestor.ingest(
            "131",
            enrich_tdocs=True,
            explicit_tdoc_list_url=str(historical_snapshot.source_url),
        )
        canonical_inventory_after_explicit = service.candidate_inventory(request)
        canonical_ids_after = [item.tdoc_id for item in repository.list_tdocs("RAN2", "131")]
        current_checksum_after = hashlib.sha256(current_path.read_bytes()).hexdigest()
        manifest_checksum_after = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

    assert len(requests) == 6
    assert manifest.download_artifacts is False
    tdoc_lists = [
        item for item in manifest.artifacts if item.artifact_type.value == "tdoc_list"
    ]
    assert {item.original_filename for item in tdoc_lists} == {
        "TDoc_List_Meeting_RAN2#131.xlsx",
        "R2-131-final-tdoc-list.xlsx",
        "tdocList_2025-09-02_14h28.xlsx",
    }
    assert all(item.retrieved_at for item in tdoc_lists)
    assert len(manifest.tdoc_list_parses) == 3
    assert len(manifest.tdoc_list_snapshots) == 3
    assert manifest.current_output is not None
    assert all(item.normalized_output is not None for item in manifest.tdoc_list_snapshots)
    assert '"tdocs":' not in manifest_path.read_text(encoding="utf-8")
    hydrated = ManifestStore.read(manifest_path)
    assert len(hydrated.tdocs) == len(manifest.tdocs)
    assert all(item.tdocs for item in hydrated.tdoc_list_snapshots)
    assert str(manifest.current_snapshot_url).endswith(
        "/Docs/TDoc_List_Meeting_RAN2%23131.xlsx"
    )
    assert str(manifest.meeting_close_snapshot_url).endswith(
        "/Tdoclists/R2-131-final-tdoc-list.xlsx"
    )
    assert enriched is not None
    assert enriched.title == "Current uplink title"
    assert enriched.abstract == "Close abstract"
    assert enriched.status == "treated"
    assert enriched.organizations == ["Nokia"]
    assert enriched.metadata_source_checksum
    assert historical_only is None
    assert len(stored_snapshots) == 3
    status_by_filename = {
        item.filename: item.tdocs[0].status for item in stored_snapshots
    }
    assert status_by_filename == {
        "R2-131-final-tdoc-list.xlsx": "withdrawn",
        "tdocList_2025-09-02_14h28.xlsx": "draft",
        "TDoc_List_Meeting_RAN2#131.xlsx": "treated",
    }
    assert any(
        item.tdoc_id == "R2-2505999"
        for snapshot in stored_snapshots
        for item in snapshot.tdocs
    )
    assert historical_inventory.view.kind.value == "historical_snapshot"
    assert historical_inventory.view.request_selected is True
    assert historical_inventory.view.canonical_current_modified is False
    assert historical_inventory.candidate_count == 2
    assert meeting_close_inventory.view.kind.value == "meeting_close"
    assert meeting_close_inventory.candidate_count == 1
    assert canonical_inventory.view.kind.value == "canonical_current"
    assert canonical_inventory.candidate_count == len(canonical_ids_before)
    assert canonical_inventory_after_explicit.view.kind.value == "canonical_current"
    assert canonical_inventory_after_explicit.candidate_count == len(canonical_ids_before)
    assert canonical_ids_after == canonical_ids_before
    assert current_checksum_after == current_checksum_before == manifest.current_output.sha256
    assert manifest_checksum_after == manifest_checksum_before
    assert explicit_manifest.current_snapshot_url == manifest.current_snapshot_url
    assert explicit_manifest.current_output == manifest.current_output
    assert explicit_manifest.request_selected_snapshot_url == historical_snapshot.source_url
    assert explicit_manifest_path != manifest_path
    assert '"tdocs":' not in explicit_manifest_path.read_text(encoding="utf-8")
    client.close()
